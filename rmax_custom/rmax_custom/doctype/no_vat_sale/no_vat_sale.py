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

	def before_insert(self):
		# New docs always start as Draft regardless of what the client sent.
		if not self.approval_status:
			self.approval_status = "Draft"

	def validate(self):
		self._resolve_accounts()
		self._populate_valuation_rates()
		self._compute_totals()
		self._validate_branch_warehouse_match()
		self._validate_stock_availability()
		self._guard_submit_status()

	def before_submit(self):
		# Submission only allowed when explicitly approved via the
		# whitelisted approve API. This protects against direct submits
		# from /api/method/frappe.client.submit.
		if self.approval_status != "Approved":
			frappe.throw(
				_("No VAT Sale {0} must be Approved before it can be submitted.").format(self.name)
			)

	def on_update(self):
		# Side-effects when status flips to Pending Approval — assign
		# ToDo + email approver. Idempotent: skip if ToDo already exists.
		if self.approval_status == "Pending Approval":
			self._notify_approver()

	def on_submit(self):
		je_name = self._create_journal_entry()
		se_name = self._create_stock_entry()
		self.db_set("journal_entry", je_name, update_modified=False)
		self.db_set("stock_entry", se_name, update_modified=False)
		self._close_approval_todos()

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
		"""Warehouse must (a) belong to the selected Company, and
		(b) appear in Branch Configuration → Warehouse for the selected Branch.

		Branch Configuration is keyed by branch (autoname), so we look up
		the child rows directly.
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

		permitted = _branch_warehouses(self.branch)
		if permitted and self.warehouse not in permitted:
			frappe.throw(
				_("Warehouse {0} is not configured under Branch {1}. "
				  "Open Branch Configuration → {1} to add it, or pick another warehouse.")
				.format(self.warehouse, self.branch)
			)

	def _guard_submit_status(self):
		# Final safety net — Approved + draft only happens via approve API.
		# If a save flips the status back to Draft on a submitted doc,
		# Frappe blocks via docstatus anyway.
		if self.docstatus == 0 and self.approval_status not in (
			"Draft",
			"Pending Approval",
			"Approved",
			"Rejected",
		):
			self.approval_status = "Draft"

	# -- Approval flow ---------------------------------------------------

	def _notify_approver(self):
		if not self.approved_by:
			return
		todo_filters = {
			"reference_type": self.doctype,
			"reference_name": self.name,
			"allocated_to": self.approved_by,
			"status": "Open",
		}
		if frappe.db.exists("ToDo", todo_filters):
			return

		desc = _(
			"No VAT Sale {0} is awaiting your approval — Branch {1}, "
			"Selling {2}, Cost {3}."
		).format(
			self.name,
			self.branch or "",
			self.total_selling_value or 0,
			self.total_cost_value or 0,
		)
		try:
			from frappe.desk.form.assign_to import add as assign_to_user
			assign_to_user(
				{
					"assign_to": [self.approved_by],
					"doctype": self.doctype,
					"name": self.name,
					"description": desc,
					"notify": 1,
				}
			)
		except Exception:
			# Fall back to a manual ToDo + email if the assign helper bombs.
			frappe.get_doc({
				"doctype": "ToDo",
				"allocated_to": self.approved_by,
				"reference_type": self.doctype,
				"reference_name": self.name,
				"description": desc,
				"status": "Open",
				"priority": "Medium",
			}).insert(ignore_permissions=True)
			try:
				frappe.sendmail(
					recipients=[self.approved_by],
					subject=_("No VAT Sale {0} pending approval").format(self.name),
					message=desc,
					reference_doctype=self.doctype,
					reference_name=self.name,
				)
			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					f"rmax_custom: NVS approver notify failed {self.name}",
				)

	def _close_approval_todos(self):
		todos = frappe.get_all(
			"ToDo",
			filters={
				"reference_type": self.doctype,
				"reference_name": self.name,
				"status": "Open",
			},
			pluck="name",
		)
		for todo in todos:
			frappe.db.set_value("ToDo", todo, "status", "Closed", update_modified=False)

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


# ---------------------------------------------------------------------------
# Branch → Warehouse filter
# ---------------------------------------------------------------------------


def _branch_warehouses(branch: str) -> list[str]:
	if not branch:
		return []
	rows = frappe.get_all(
		"Branch Configuration Warehouse",
		filters={"parent": branch, "parenttype": "Branch Configuration"},
		pluck="warehouse",
	)
	# Drop blank rows + dedupe while preserving order.
	seen, out = set(), []
	for w in rows:
		if w and w not in seen:
			seen.add(w)
			out.append(w)
	return out


@frappe.whitelist()
def get_branch_warehouses(branch: str) -> list[str]:
	"""Whitelisted: return Warehouse names listed under the given Branch's
	Branch Configuration child table. Used by the form to filter the
	warehouse dropdown."""
	return _branch_warehouses(branch)


# ---------------------------------------------------------------------------
# Approval workflow APIs
# ---------------------------------------------------------------------------


def _assert_can_approve(doc: "NoVATSale"):
	user = frappe.session.user
	if user == "Administrator":
		return
	if user == doc.approved_by:
		return
	# Sales Manager / System Manager can act on any NVS as a fallback.
	roles = set(frappe.get_roles(user))
	if roles & {"Sales Manager", "System Manager"}:
		return
	frappe.throw(
		_("Only the named Approver ({0}) can approve or reject this No VAT Sale.")
		.format(doc.approved_by or "—")
	)


@frappe.whitelist()
def submit_for_approval(name: str) -> dict:
	"""Move a Draft NVS into 'Pending Approval'. Notifies the approver."""
	doc = frappe.get_doc("No VAT Sale", name)
	if doc.docstatus != 0:
		frappe.throw(_("Only Draft documents can be sent for approval."))
	if doc.approval_status == "Pending Approval":
		return {"status": doc.approval_status}
	if not doc.approved_by:
		frappe.throw(_("Set 'Approved By' before sending for approval."))

	doc.approval_status = "Pending Approval"
	doc.save()
	return {"status": doc.approval_status}


@frappe.whitelist()
def approve_no_vat_sale(name: str, remarks: str | None = None) -> dict:
	"""Approve + submit. Only the named approver (or Sales/System Mgr) can call."""
	doc = frappe.get_doc("No VAT Sale", name)
	if doc.docstatus != 0:
		frappe.throw(_("Only Draft documents can be approved."))
	if doc.approval_status not in ("Pending Approval", "Draft"):
		frappe.throw(
			_("Cannot approve from status {0}.").format(doc.approval_status)
		)
	_assert_can_approve(doc)

	if remarks:
		doc.approval_remarks = remarks
	doc.approval_status = "Approved"
	# Bypass DocPerm submit check — the role gate is _assert_can_approve.
	doc.flags.ignore_permissions = True
	doc.submit()
	return {"status": doc.approval_status, "name": doc.name}


@frappe.whitelist()
def reject_no_vat_sale(name: str, remarks: str | None = None) -> dict:
	"""Reject — keeps the doc as Draft with status=Rejected."""
	doc = frappe.get_doc("No VAT Sale", name)
	if doc.docstatus != 0:
		frappe.throw(_("Only Draft documents can be rejected."))
	_assert_can_approve(doc)

	if remarks:
		doc.approval_remarks = remarks
	doc.approval_status = "Rejected"
	doc.save()
	# Close any pending ToDos so the approver's queue clears.
	for todo in frappe.get_all(
		"ToDo",
		filters={
			"reference_type": "No VAT Sale",
			"reference_name": doc.name,
			"status": "Open",
		},
		pluck="name",
	):
		frappe.db.set_value("ToDo", todo, "status", "Closed", update_modified=False)
	return {"status": doc.approval_status, "name": doc.name}
