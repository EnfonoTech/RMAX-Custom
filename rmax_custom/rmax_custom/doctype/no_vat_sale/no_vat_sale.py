# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""No VAT Sale — dedicated doctype for cash sales that bypass VAT.

Instead of a standard Sales Invoice (which requires VAT), this doctype
posts the two journal entries described in the client's 'NO VAT Sale
Workflow' document:

  1. Cash Receipt:
     Dr Cash / Bank
        Cr Naseef (revenue control)

  2. Inventory Outflow:
     Dr Damage Written Off (COGS)
        Cr Inventory    <-- via Stock Entry Material Issue

A single submission of the No VAT Sale creates both the Journal Entry
and the Stock Entry automatically, stamps them on the doc, and links
cancellation back to them.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime


PRICE_LIST = "No VAT Price"


class NoVATSale(Document):

	# -- Lifecycle --------------------------------------------------------

	def validate(self):
		self._resolve_accounts()
		self._populate_valuation_rates()
		self._compute_totals()
		self._validate_branch_warehouse_match()
		self._validate_stock_availability()

	def on_submit(self):
		je_name = self._create_journal_entry()
		se_name = self._create_stock_entry()
		self.db_set("journal_entry", je_name, update_modified=False)
		self.db_set("stock_entry", se_name, update_modified=False)

	def on_cancel(self):
		# Cancel dependent docs
		for dt, name in (("Stock Entry", self.stock_entry), ("Journal Entry", self.journal_entry)):
			if not name:
				continue
			if not frappe.db.exists(dt, name):
				continue
			doc = frappe.get_doc(dt, name)
			if doc.docstatus == 1:
				doc.cancel()

	# -- Helpers ----------------------------------------------------------

	def _resolve_accounts(self):
		if not self.company:
			return

		# Use db.get_value to bypass per-doctype read checks — these
		# account fields are configuration, not user-editable here.
		naseef = frappe.db.get_value("Company", self.company, "custom_novat_naseef_account")
		cogs = frappe.db.get_value("Company", self.company, "custom_novat_cogs_account")
		if not naseef:
			frappe.throw(
				_("Set 'NO VAT Naseef Account' on Company {0} before creating a No VAT Sale.").format(self.company)
			)
		if not cogs:
			frappe.throw(
				_("Set 'NO VAT Damage Written Off Account' on Company {0} before creating a No VAT Sale.").format(self.company)
			)
		self.naseef_account = naseef
		self.cogs_account = cogs

		# Cash account from Mode of Payment default account for this company
		if self.mode_of_payment:
			default_account = frappe.db.get_value(
				"Mode of Payment Account",
				{"parent": self.mode_of_payment, "company": self.company},
				"default_account",
			)
			if default_account:
				self.cash_account = default_account
		if not self.cash_account:
			frappe.throw(
				_(
					"No default account mapped for Mode of Payment {0} on Company {1}. "
					"Open Mode of Payment → Accounts and add a row for this company."
				).format(self.mode_of_payment, self.company)
			)

	def _populate_valuation_rates(self):
		"""Fetch moving-average valuation rate per item from Bin."""
		if not self.warehouse:
			return
		for row in self.items:
			if not row.item_code:
				continue
			val_rate = frappe.db.get_value(
				"Bin",
				{"item_code": row.item_code, "warehouse": self.warehouse},
				"valuation_rate",
			)
			if not val_rate:
				# Fallback to Item valuation rate
				val_rate = frappe.db.get_value("Item", row.item_code, "valuation_rate")
			row.valuation_rate = flt(val_rate)
			row.cost_amount = flt(row.valuation_rate) * flt(row.qty)

	def _compute_totals(self):
		total_selling = 0.0
		total_cost = 0.0
		for row in self.items:
			row.amount = flt(row.rate) * flt(row.qty)
			total_selling += row.amount
			total_cost += flt(row.cost_amount)
		self.total_selling_value = total_selling
		self.total_cost_value = total_cost
		self.gross_profit = total_selling - total_cost

	def _validate_branch_warehouse_match(self):
		"""Warehouse must belong to the same Company as the selected Branch.

		Core ERPNext Warehouse has no `branch` field, so we cross-check by
		Company instead. If a site adds a custom `branch` link on
		Warehouse later, this check still passes harmlessly.
		"""
		if not (self.branch and self.warehouse):
			return
		wh_company = frappe.db.get_value("Warehouse", self.warehouse, "company")
		if wh_company and wh_company != self.company:
			frappe.throw(
				_("Warehouse {0} belongs to company {1}, not {2}.").format(
					self.warehouse, wh_company, self.company
				)
			)

	def _validate_stock_availability(self):
		if not self.warehouse:
			return
		for row in self.items:
			if not row.item_code:
				continue
			available = frappe.db.get_value(
				"Bin",
				{"item_code": row.item_code, "warehouse": self.warehouse},
				"actual_qty",
			) or 0
			if flt(row.qty) > flt(available):
				frappe.throw(
					_("Insufficient stock for {0} in {1}: available {2}, requested {3}.").format(
						row.item_code, self.warehouse, available, row.qty
					)
				)

	# -- Sub-document creation -------------------------------------------

	def _create_journal_entry(self) -> str:
		"""Dr Cash  /  Cr Naseef — records cash inflow and sales value."""
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Cash Entry"
		je.company = self.company
		je.posting_date = self.posting_date
		je.cheque_no = self.name
		je.cheque_date = self.posting_date
		je.user_remark = f"NO VAT Sale {self.name} — {self.branch}"
		je.append("accounts", {
			"account": self.cash_account,
			"debit_in_account_currency": flt(self.total_selling_value),
			"credit_in_account_currency": 0,
		})
		je.append("accounts", {
			"account": self.naseef_account,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": flt(self.total_selling_value),
		})
		je.custom_no_vat_sale = self.name
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()
		return je.name

	def _create_stock_entry(self) -> str:
		"""Material Issue reducing stock; expense account = COGS / Damage Written Off."""
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Issue"
		se.purpose = "Material Issue"
		se.company = self.company
		se.posting_date = self.posting_date
		se.posting_time = self.posting_time
		se.from_warehouse = self.warehouse
		se.remarks = f"NO VAT Sale {self.name} — {self.branch}"

		company_cost_center = frappe.db.get_value("Company", self.company, "cost_center")

		for row in self.items:
			se.append("items", {
				"item_code": row.item_code,
				"qty": row.qty,
				"uom": row.uom,
				"stock_uom": row.stock_uom,
				"conversion_factor": row.conversion_factor or 1,
				"s_warehouse": self.warehouse,
				"basic_rate": flt(row.valuation_rate),
				"expense_account": self.cogs_account,
				"cost_center": company_cost_center,
			})

		se.custom_no_vat_sale = self.name
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		return se.name


# ---------------------------------------------------------------------------
# Whitelisted APIs (client-side rate fetch)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_item_rate(item_code: str, price_list: str | None = None) -> float:
	"""Fetch selling rate from the No VAT price list (or passed price list)."""
	pl = price_list or PRICE_LIST
	rate = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": pl, "selling": 1},
		"price_list_rate",
	)
	return flt(rate)


@frappe.whitelist()
def get_default_accounts(company: str, mode_of_payment: str | None = None) -> dict:
	"""Return naseef, cogs and cash_account for the form to prefill.

	Uses db.get_value internally so non-admin roles aren't blocked by
	doc-level read permissions on Company / Mode of Payment.
	"""
	if not company:
		return {}

	result = {
		"naseef_account": frappe.db.get_value(
			"Company", company, "custom_novat_naseef_account"
		),
		"cogs_account": frappe.db.get_value(
			"Company", company, "custom_novat_cogs_account"
		),
	}
	if mode_of_payment:
		result["cash_account"] = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": mode_of_payment, "company": company},
			"default_account",
		)
	return result


@frappe.whitelist()
def get_item_valuation(item_code: str, warehouse: str) -> float:
	rate = frappe.db.get_value(
		"Bin",
		{"item_code": item_code, "warehouse": warehouse},
		"valuation_rate",
	)
	if not rate:
		rate = frappe.db.get_value("Item", item_code, "valuation_rate")
	return flt(rate)
