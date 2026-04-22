# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""LCV Charge Template wiring.

Parts:
* after_migrate setup — idempotent creation of the LCV expense accounts
  (per Company) and the default 'Standard Import KSA' template.
* Purchase Receipt validate hook — auto-populate checklist from the
  selected template if empty, and refresh per-PR status.
* Landed Cost Voucher on_submit / on_cancel hooks — mark checklist rows
  done / undone and recompute PR status.
* Whitelisted APIs — load_template_into_pr, create_lcv_from_template.
"""

from typing import Dict, List, Optional

import frappe
from frappe import _
from frappe.utils import flt


DEFAULT_TEMPLATE_NAME = "Standard Import KSA"
LCV_PARENT_GROUP = "Landed Cost Charges"

# Charges shipped with the default template.
# distribute_by is RMAX vocabulary; 'Value' maps to ERPNext 'Distribute Charges Based On = Amount'
# (keeping Distribute Manually + custom_distribute_by_cbm for CBM rows).
# default_amount intentionally omitted — amounts vary per shipment.
DEFAULT_CHARGES: List[Dict] = [
	{"charge_name": "Freight Sea/Air",            "currency": "USD", "distribute_by": "CBM"},
	{"charge_name": "Duty",                       "currency": "SAR", "distribute_by": "Value"},
	{"charge_name": "DO Charges",                 "currency": "SAR", "distribute_by": "CBM"},
	{"charge_name": "Port Charges",               "currency": "SAR", "distribute_by": "CBM"},
	{"charge_name": "Mawani",                     "currency": "SAR", "distribute_by": "CBM"},
	{"charge_name": "Fasah Appointment Fees",     "currency": "SAR", "distribute_by": "CBM"},
	{"charge_name": "Custom Clearance Charges",   "currency": "SAR", "distribute_by": "CBM"},
	{"charge_name": "Transportation to Warehouse","currency": "SAR", "distribute_by": "CBM"},
	{"charge_name": "Doc Charges",                "currency": "SAR", "distribute_by": "CBM"},
	{"charge_name": "Local Unloading Expense",    "currency": "SAR", "distribute_by": "CBM"},
	{"charge_name": "Overtime (Kafeel)",          "currency": "SAR", "distribute_by": "CBM"},
]


# ---------------------------------------------------------------------------
# after_migrate setup
# ---------------------------------------------------------------------------


def setup_lcv_defaults():
	"""Create expense accounts per company + ship default template + backfill custom-field flags."""
	_ensure_accounts_per_company()
	_ensure_default_template()
	_upgrade_default_template()
	_ensure_allow_on_submit_flags()


def _ensure_allow_on_submit_flags():
	"""Make the PR LCV fields editable after PR submission.

	Without this flag Frappe blocks user-picked templates on already-
	submitted PRs ('Not allowed to change LCV Charge Template after
	submission').
	"""
	fields = [
		"Purchase Receipt-custom_lcv_template",
		"Purchase Receipt-custom_lcv_status",
		"Purchase Receipt-custom_lcv_checklist",
	]
	for name in fields:
		if not frappe.db.exists("Custom Field", name):
			continue
		frappe.db.set_value("Custom Field", name, "allow_on_submit", 1, update_modified=False)
	frappe.db.commit()
	frappe.clear_cache(doctype="Purchase Receipt")


def _upgrade_default_template():
	"""Ensure every shipped charge row is present in the default template.

	Adds missing rows (e.g. Duty introduced later), clears the old sample
	default_amount values (they were image examples, not real defaults),
	and never touches rows a user has manually added.
	"""
	if not frappe.db.exists("LCV Charge Template", DEFAULT_TEMPLATE_NAME):
		return

	tmpl = frappe.get_doc("LCV Charge Template", DEFAULT_TEMPLATE_NAME)
	existing_names = {row.charge_name for row in tmpl.charges}
	shipped_names = {c["charge_name"] for c in DEFAULT_CHARGES}

	dirty = False

	# Add missing shipped charges
	for charge in DEFAULT_CHARGES:
		if charge["charge_name"] in existing_names:
			continue
		tmpl.append("charges", {
			"charge_name": charge["charge_name"],
			"currency": charge["currency"],
			"distribute_by": charge["distribute_by"],
			"is_mandatory": 0,
		})
		dirty = True

	# Clear legacy sample default_amount on shipped rows
	for row in tmpl.charges:
		if row.charge_name in shipped_names and row.default_amount:
			row.default_amount = 0
			dirty = True

	# Also keep currency/distribute_by aligned with the shipped definition
	shipped_meta = {c["charge_name"]: c for c in DEFAULT_CHARGES}
	for row in tmpl.charges:
		meta = shipped_meta.get(row.charge_name)
		if not meta:
			continue
		if row.currency != meta["currency"]:
			row.currency = meta["currency"]
			dirty = True
		if row.distribute_by != meta["distribute_by"]:
			row.distribute_by = meta["distribute_by"]
			dirty = True

	if dirty:
		tmpl.save(ignore_permissions=True)
		frappe.db.commit()


def _ensure_accounts_per_company():
	# Only root companies — ERPNext syncs to child companies automatically.
	root_companies = frappe.get_all(
		"Company",
		filters=[["parent_company", "in", ["", None]]],
		fields=["name", "abbr"],
	)

	for company in root_companies:
		parent = _ensure_parent_group(company.name, company.abbr)
		if not parent:
			continue

		for charge in DEFAULT_CHARGES:
			account_name = f"{charge['charge_name']} - {company.abbr}"
			if frappe.db.exists("Account", account_name):
				_align_account_currency(account_name, charge.get("currency"))
				continue
			try:
				payload = {
					"doctype": "Account",
					"account_name": charge["charge_name"],
					"parent_account": parent,
					"company": company.name,
					"account_type": "Expense Account",
					"root_type": "Expense",
					"is_group": 0,
				}
				# USD freight needs the account booked in USD so LCV tax row
				# offers exchange_rate to SAR company base.
				if charge.get("currency"):
					payload["account_currency"] = charge["currency"]

				frappe.get_doc(payload).insert(ignore_permissions=True)
			except Exception:
				# Don't let one bad account block the rest; log and move on.
				frappe.log_error(
					frappe.get_traceback(),
					f"rmax_custom lcv_template: failed to create {account_name}",
				)

	frappe.db.commit()


def _align_account_currency(account_name: str, desired_currency: Optional[str]):
	"""If an existing RMAX-shipped account has the wrong currency, fix it.

	Only runs when the account has never been used (no GL entry).
	"""
	if not desired_currency:
		return

	current = frappe.db.get_value("Account", account_name, "account_currency")
	if current == desired_currency:
		return

	# Safety: only change currency if the account has never been posted to
	has_gl = frappe.db.exists("GL Entry", {"account": account_name})
	if has_gl:
		return

	frappe.db.set_value(
		"Account",
		account_name,
		"account_currency",
		desired_currency,
		update_modified=False,
	)


def _ensure_parent_group(company: str, abbr: str) -> Optional[str]:
	"""Return name of the Landed Cost Charges group account under Indirect Expenses."""
	parent_name = f"{LCV_PARENT_GROUP} - {abbr}"
	if frappe.db.exists("Account", parent_name):
		return parent_name

	# Parent: Indirect Expenses group
	indirect_expenses = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": "Indirect Expenses", "is_group": 1},
		"name",
	) or frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Expense", "is_group": 1},
		"name",
	)
	if not indirect_expenses:
		return None

	try:
		frappe.get_doc({
			"doctype": "Account",
			"account_name": LCV_PARENT_GROUP,
			"parent_account": indirect_expenses,
			"company": company,
			"is_group": 1,
			"root_type": "Expense",
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			f"rmax_custom lcv_template: failed to create parent group for {company}",
		)
		return None
	return parent_name


def _ensure_default_template():
	if frappe.db.exists("LCV Charge Template", DEFAULT_TEMPLATE_NAME):
		return

	doc = frappe.get_doc({
		"doctype": "LCV Charge Template",
		"template_name": DEFAULT_TEMPLATE_NAME,
		"is_default": 1,
		"charges": [
			{
				"charge_name": c["charge_name"],
				"currency": c["currency"],
				"distribute_by": c["distribute_by"],
				"is_mandatory": 0,
			}
			for c in DEFAULT_CHARGES
		],
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()


# ---------------------------------------------------------------------------
# Purchase Receipt hooks
# ---------------------------------------------------------------------------


def purchase_receipt_validate(doc, method=None):
	"""Auto-populate checklist from template if empty; refresh status."""
	if doc.get("custom_lcv_template") and not doc.get("custom_lcv_checklist"):
		_populate_checklist(doc)
	_refresh_status(doc)


def _populate_checklist(pr_doc):
	template_name = pr_doc.get("custom_lcv_template")
	if not template_name:
		return
	if not frappe.db.exists("LCV Charge Template", template_name):
		return

	template = frappe.get_doc("LCV Charge Template", template_name)
	company_abbr = frappe.db.get_value("Company", pr_doc.company, "abbr")

	for row in template.charges:
		account_name = f"{row.charge_name} - {company_abbr}" if company_abbr else None
		if account_name and not frappe.db.exists("Account", account_name):
			account_name = None

		pr_doc.append("custom_lcv_checklist", {
			"charge_name": row.charge_name,
			"expense_account": account_name,
			"distribute_by": row.distribute_by,
			"is_mandatory": row.is_mandatory,
			"done": 0,
			"lcv_reference": None,
			"amount": 0,
		})


def _refresh_status(pr_doc):
	checklist = pr_doc.get("custom_lcv_checklist") or []
	if not checklist:
		pr_doc.custom_lcv_status = "Not Started"
		return

	total = len(checklist)
	done = sum(1 for r in checklist if r.done)
	mandatory_total = sum(1 for r in checklist if r.is_mandatory)
	mandatory_done = sum(1 for r in checklist if r.is_mandatory and r.done)

	if done == 0:
		pr_doc.custom_lcv_status = "Not Started"
	elif done == total:
		pr_doc.custom_lcv_status = "Complete"
	elif mandatory_total and mandatory_done == mandatory_total:
		pr_doc.custom_lcv_status = "Partial"
	else:
		pr_doc.custom_lcv_status = "Pending"


# ---------------------------------------------------------------------------
# Landed Cost Voucher hooks
# ---------------------------------------------------------------------------


def landed_cost_voucher_on_submit(doc, method=None):
	_apply_lcv_to_linked_prs(doc, mark_done=True)


def landed_cost_voucher_on_cancel(doc, method=None):
	_apply_lcv_to_linked_prs(doc, mark_done=False)


def _apply_lcv_to_linked_prs(lcv_doc, mark_done: bool):
	receipts = [
		r.receipt_document
		for r in (lcv_doc.get("purchase_receipts") or [])
		if r.receipt_document_type == "Purchase Receipt"
	]

	# Aggregate LCV amounts by expense account
	account_amounts: Dict[str, float] = {}
	for tax in (lcv_doc.get("taxes") or []):
		if not tax.expense_account:
			continue
		account_amounts[tax.expense_account] = account_amounts.get(tax.expense_account, 0.0) + flt(tax.amount)

	for pr_name in receipts:
		try:
			pr = frappe.get_doc("Purchase Receipt", pr_name)
		except frappe.DoesNotExistError:
			continue

		checklist = pr.get("custom_lcv_checklist") or []
		if not checklist:
			continue

		dirty = False
		for row in checklist:
			if not row.expense_account or row.expense_account not in account_amounts:
				continue

			if mark_done:
				if row.done and row.lcv_reference and row.lcv_reference != lcv_doc.name:
					# Already booked by a different LCV — don't clobber
					continue
				row.done = 1
				row.lcv_reference = lcv_doc.name
				row.amount = account_amounts[row.expense_account]
				dirty = True
			else:
				if row.lcv_reference == lcv_doc.name:
					row.done = 0
					row.lcv_reference = None
					row.amount = 0
					dirty = True

		if dirty:
			_refresh_status(pr)
			pr.db_update()
			for row in checklist:
				row.db_update()
			# Recompute status on PR record
			frappe.db.set_value(
				"Purchase Receipt",
				pr.name,
				"custom_lcv_status",
				pr.custom_lcv_status,
				update_modified=False,
			)

	frappe.db.commit()


# ---------------------------------------------------------------------------
# Whitelisted APIs
# ---------------------------------------------------------------------------


@frappe.whitelist()
def load_template_into_pr(purchase_receipt: str, template: str):
	"""Explicit button handler to (re)load template rows into a PR checklist."""
	if not frappe.db.exists("Purchase Receipt", purchase_receipt):
		frappe.throw(_("Purchase Receipt {0} not found").format(purchase_receipt))
	pr = frappe.get_doc("Purchase Receipt", purchase_receipt)

	pr.custom_lcv_template = template
	# Reset checklist — user explicitly opted in
	pr.set("custom_lcv_checklist", [])
	_populate_checklist(pr)
	_refresh_status(pr)
	pr.save(ignore_permissions=False)
	return {"status": pr.custom_lcv_status, "rows": len(pr.custom_lcv_checklist)}


@frappe.whitelist()
def create_lcv_from_template(purchase_receipt: str):
	"""Create a Draft Landed Cost Voucher pre-filled from the PR's checklist.

	Only rows that are not yet done are included so users can iteratively
	add the remaining charges.
	"""
	if not frappe.db.exists("Purchase Receipt", purchase_receipt):
		frappe.throw(_("Purchase Receipt {0} not found").format(purchase_receipt))

	pr = frappe.get_doc("Purchase Receipt", purchase_receipt)
	checklist = pr.get("custom_lcv_checklist") or []
	pending_rows = [r for r in checklist if not r.done and r.expense_account]
	if not pending_rows:
		frappe.throw(_("No pending charges for this Purchase Receipt."))

	# If all pending rows are CBM, use Distribute Manually + custom CBM.
	# If mixed or any Value, fall back to Distribute Manually (manual amounts)
	# — user must still set correct distribution per their workflow.
	all_cbm = all(r.distribute_by == "CBM" for r in pending_rows)

	lcv = frappe.new_doc("Landed Cost Voucher")
	lcv.company = pr.company
	lcv.posting_date = frappe.utils.today()
	lcv.distribute_charges_based_on = "Distribute Manually"
	if all_cbm:
		lcv.custom_distribute_by_cbm = 1

	lcv.append("purchase_receipts", {
		"receipt_document_type": "Purchase Receipt",
		"receipt_document": pr.name,
		"supplier": pr.supplier,
		"posting_date": pr.posting_date,
		"grand_total": pr.grand_total,
	})

	for row in pending_rows:
		# Resolve amount from the template (default_amount) if checklist has 0
		amount = flt(row.amount)
		if not amount:
			amount = _template_default_amount(pr.custom_lcv_template, row.charge_name)
		lcv.append("taxes", {
			"expense_account": row.expense_account,
			"description": row.charge_name,
			"amount": amount,
		})

	lcv.insert(ignore_permissions=False)
	return lcv.name


def _template_default_amount(template_name: Optional[str], charge_name: str) -> float:
	if not template_name:
		return 0.0
	row = frappe.db.get_value(
		"LCV Charge Template Item",
		{"parent": template_name, "charge_name": charge_name},
		"default_amount",
	)
	return flt(row or 0)
