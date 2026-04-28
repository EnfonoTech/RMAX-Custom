# Copyright (c) 2026, Enfono Technologies and contributors
# For license information, please see license.txt

"""BNPL Settlement controller.

Posts the bank-side leg of a Tabby/Tamara settlement. The Sales Invoice
already credited the provider clearing account at gross. This document
moves that gross balance into Bank (net) + BNPL Fee Expense (commission)
via an auto-created Journal Entry, and stamps every linked Sales Invoice
as settled for reporting.

See: Tabby RMAX BRD §3.4 (COGS untouched) + Phase 2 settlement workflow.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


SURCHARGE_FIELD = "custom_surcharge_percentage"
ROUNDING_TOLERANCE = 0.01


class BNPLSettlement(Document):
	def autoname(self):
		# naming_series handles it; controller hook reserved for future use.
		pass

	def validate(self):
		self._validate_mode_of_payment()
		self._fetch_default_accounts()
		self._populate_invoice_metadata()
		self._validate_invoice_rows()
		self._calculate_totals()

	def before_submit(self):
		if not self.invoices:
			frappe.throw(_("Cannot submit a BNPL Settlement with no invoices."))
		if flt(self.gross_amount) <= 0:
			frappe.throw(_("Gross Amount must be positive."))
		if flt(self.fee_amount) < 0:
			frappe.throw(_("Provider Fee cannot be negative."))
		if flt(self.fee_amount) > flt(self.gross_amount):
			frappe.throw(_("Provider Fee cannot exceed the Gross Amount."))

	def on_submit(self):
		jv = self._create_journal_entry()
		self.db_set("journal_entry", jv.name)
		self.db_set("status", "Submitted")
		self._mark_invoices_settled()

	def on_cancel(self):
		self._unmark_invoices_settled()
		if self.journal_entry:
			try:
				jv = frappe.get_doc("Journal Entry", self.journal_entry)
				if jv.docstatus == 1:
					jv.cancel()
			except frappe.DoesNotExistError:
				pass
		self.db_set("status", "Cancelled")

	# ------------------------------------------------------------------
	# Validation helpers
	# ------------------------------------------------------------------

	def _validate_mode_of_payment(self):
		if not self.mode_of_payment:
			return
		surcharge = flt(
			frappe.db.get_value("Mode of Payment", self.mode_of_payment, SURCHARGE_FIELD)
		)
		if surcharge <= 0:
			frappe.throw(
				_(
					"Mode of Payment {0} has no Surcharge Percentage configured. "
					"BNPL Settlement is only meant for BNPL providers (Tabby, Tamara)."
				).format(self.mode_of_payment),
				title=_("Not a BNPL Mode of Payment"),
			)

	def _fetch_default_accounts(self):
		if self.mode_of_payment and not self.clearing_account:
			self.clearing_account = frappe.db.get_value(
				"Mode of Payment", self.mode_of_payment, "custom_bnpl_clearing_account"
			)
		if self.company and not self.fee_account:
			self.fee_account = frappe.db.get_value(
				"Company", self.company, "custom_bnpl_fee_account"
			)

	def _populate_invoice_metadata(self):
		"""Auto-fill bnpl_uplift_amount + default allocated_amount from the SI."""
		if not self.invoices:
			return

		surcharge_pct = flt(
			frappe.db.get_value("Mode of Payment", self.mode_of_payment, SURCHARGE_FIELD)
		)
		factor = 1 + surcharge_pct / 100.0 if surcharge_pct else 1.0

		for row in self.invoices:
			if not row.sales_invoice:
				continue
			si = frappe.db.get_value(
				"Sales Invoice",
				row.sales_invoice,
				[
					"docstatus",
					"company",
					"customer",
					"posting_date",
					"grand_total",
					"customer_name",
					"custom_bnpl_settled",
					"custom_bnpl_settlement",
				],
				as_dict=True,
			)
			if not si:
				frappe.throw(
					_("Sales Invoice {0} not found.").format(row.sales_invoice)
				)

			row.posting_date = si.posting_date
			row.customer = si.customer
			row.customer_name = si.customer_name
			row.grand_total = si.grand_total

			uplift = flt(
				frappe.db.sql(
					"""
					SELECT COALESCE(SUM(custom_bnpl_uplift_amount), 0)
					FROM `tabSales Invoice Item`
					WHERE parent = %s
					""",
					row.sales_invoice,
				)[0][0]
			)
			row.bnpl_uplift_amount = uplift

			bnpl_payment_amount = flt(
				frappe.db.sql(
					"""
					SELECT COALESCE(SUM(amount), 0)
					FROM `tabSales Invoice Payment`
					WHERE parent = %s AND mode_of_payment = %s
					""",
					(row.sales_invoice, self.mode_of_payment),
				)[0][0]
			)

			if bnpl_payment_amount <= 0:
				frappe.throw(
					_(
						"Sales Invoice {0} does not have a payment row for {1}. "
						"Either remove it from the table or pick the correct Mode of Payment."
					).format(row.sales_invoice, self.mode_of_payment)
				)

			if not flt(row.allocated_amount):
				row.allocated_amount = bnpl_payment_amount

	def _validate_invoice_rows(self):
		seen = set()
		for row in self.invoices:
			if not row.sales_invoice:
				continue

			if row.sales_invoice in seen:
				frappe.throw(
					_("Sales Invoice {0} appears more than once in the table.").format(
						row.sales_invoice
					)
				)
			seen.add(row.sales_invoice)

			si = frappe.db.get_value(
				"Sales Invoice",
				row.sales_invoice,
				[
					"docstatus",
					"company",
					"custom_bnpl_settled",
					"custom_bnpl_settlement",
				],
				as_dict=True,
			)
			if not si:
				continue
			if si.docstatus != 1:
				frappe.throw(
					_("Sales Invoice {0} is not submitted.").format(row.sales_invoice)
				)
			if si.company != self.company:
				frappe.throw(
					_(
						"Sales Invoice {0} belongs to company {1}, not {2}."
					).format(row.sales_invoice, si.company, self.company)
				)
			already_settled = (
				si.custom_bnpl_settled
				and si.custom_bnpl_settlement
				and si.custom_bnpl_settlement != self.name
			)
			if already_settled:
				frappe.throw(
					_(
						"Sales Invoice {0} is already settled under {1}."
					).format(row.sales_invoice, si.custom_bnpl_settlement)
				)
			if flt(row.allocated_amount) <= 0:
				frappe.throw(
					_("Allocated Amount on row {0} must be positive.").format(row.idx)
				)

	def _calculate_totals(self):
		gross = sum(flt(r.allocated_amount) for r in (self.invoices or []))
		self.gross_amount = flt(gross, 2)
		self.net_amount = flt(self.gross_amount - flt(self.fee_amount), 2)

	# ------------------------------------------------------------------
	# Journal Entry posting
	# ------------------------------------------------------------------

	def _create_journal_entry(self):
		gross = flt(self.gross_amount)
		fee = flt(self.fee_amount)
		net = flt(self.net_amount)

		if abs((net + fee) - gross) > ROUNDING_TOLERANCE:
			frappe.throw(
				_("Internal error: Net + Fee does not equal Gross. Re-check amounts.")
			)

		jv = frappe.new_doc("Journal Entry")
		jv.voucher_type = "Bank Entry"
		jv.posting_date = self.settlement_date
		jv.company = self.company
		jv.cheque_no = self.reference_no or self.name
		jv.cheque_date = self.settlement_date
		jv.user_remark = _("BNPL settlement {0} for {1}").format(
			self.name, self.mode_of_payment
		)

		# Dr Bank (net)
		if net > 0:
			jv.append(
				"accounts",
				{
					"account": self.bank_account,
					"debit_in_account_currency": net,
					"credit_in_account_currency": 0,
				},
			)

		# Dr BNPL Fee Expense (commission)
		if fee > 0:
			jv.append(
				"accounts",
				{
					"account": self.fee_account,
					"debit_in_account_currency": fee,
					"credit_in_account_currency": 0,
				},
			)

		# Cr Clearing (gross)
		jv.append(
			"accounts",
			{
				"account": self.clearing_account,
				"debit_in_account_currency": 0,
				"credit_in_account_currency": gross,
			},
		)

		jv.insert(ignore_permissions=True)
		jv.submit()
		return jv

	def _mark_invoices_settled(self):
		for row in self.invoices:
			if not row.sales_invoice:
				continue
			frappe.db.set_value(
				"Sales Invoice",
				row.sales_invoice,
				{
					"custom_bnpl_settled": 1,
					"custom_bnpl_settlement": self.name,
				},
				update_modified=False,
			)

	def _unmark_invoices_settled(self):
		for row in self.invoices:
			if not row.sales_invoice:
				continue
			current = frappe.db.get_value(
				"Sales Invoice", row.sales_invoice, "custom_bnpl_settlement"
			)
			if current != self.name:
				continue
			frappe.db.set_value(
				"Sales Invoice",
				row.sales_invoice,
				{"custom_bnpl_settled": 0, "custom_bnpl_settlement": None},
				update_modified=False,
			)


# ----------------------------------------------------------------------
# Whitelisted helper APIs (used by the form for "Get Pending Invoices")
# ----------------------------------------------------------------------


@frappe.whitelist()
def get_pending_invoices(company: str, mode_of_payment: str, to_date: str | None = None):
	"""Return submitted Sales Invoices with this BNPL Mode of Payment that are
	not yet settled. Used by the BNPL Settlement form's "Fetch Invoices"
	button.
	"""
	if not company or not mode_of_payment:
		frappe.throw(_("Company and Mode of Payment are required."))

	conditions = [
		"si.docstatus = 1",
		"si.company = %(company)s",
		"COALESCE(si.custom_bnpl_settled, 0) = 0",
		"sip.mode_of_payment = %(mode_of_payment)s",
	]
	values = {"company": company, "mode_of_payment": mode_of_payment}
	if to_date:
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = to_date

	rows = frappe.db.sql(
		f"""
		SELECT
			si.name AS sales_invoice,
			si.posting_date,
			si.customer,
			si.customer_name,
			si.grand_total,
			COALESCE((
				SELECT SUM(sii.custom_bnpl_uplift_amount)
				FROM `tabSales Invoice Item` sii
				WHERE sii.parent = si.name
			), 0) AS bnpl_uplift_amount,
			COALESCE(SUM(sip.amount), 0) AS allocated_amount
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Payment` sip ON sip.parent = si.name
		WHERE {" AND ".join(conditions)}
		GROUP BY si.name
		ORDER BY si.posting_date, si.name
		""",
		values,
		as_dict=True,
	)
	return rows
