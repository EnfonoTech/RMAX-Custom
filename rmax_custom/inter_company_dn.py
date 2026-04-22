# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""Inter-Company Delivery Note → consolidated Purchase Invoice.

Operators pick multiple submitted inter-company Delivery Notes and roll
them up into a single Draft Purchase Invoice in the receiving Company.

Design:
* No auto-create on DN submit — consolidation is always explicit via
  the list action (per client requirement).
* Validation: every selected DN must be submitted, flagged
  is_internal_customer, share represents_company, share supplier, share
  currency, share custom_inter_company_branch, and not already be
  linked to another Draft/Submitted PI.
* Output PI inherits taxes from the first selected DN; cost center and
  warehouse come from the Inter Company Branch master entry that matches
  the buying Company.
* Each source DN is stamped with custom_inter_company_pi and
  custom_inter_company_status = "Consolidated". Cancelling the PI clears
  those stamps so the DNs can be rolled into a different PI.
"""

from __future__ import annotations

from typing import List

import frappe
from frappe import _
from frappe.utils import cint, flt


STATUS_NOT_CONSOLIDATED = "Not Consolidated"
STATUS_CONSOLIDATED = "Consolidated"

INTER_COMPANY_PRICE_LIST = "Inter Company Price"


def setup_inter_company_price_list():
	"""Create the 'Inter Company Price' Price List if missing. Idempotent."""
	if frappe.db.exists("Price List", INTER_COMPANY_PRICE_LIST):
		return
	try:
		frappe.get_doc({
			"doctype": "Price List",
			"price_list_name": INTER_COMPANY_PRICE_LIST,
			"currency": frappe.db.get_single_value("Global Defaults", "default_currency") or "SAR",
			"enabled": 1,
			"buying": 1,
			"selling": 1,
		}).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"rmax_custom: failed to create Inter Company Price list",
		)


# ---------------------------------------------------------------------------
# Whitelisted API — called from Delivery Note list action
# ---------------------------------------------------------------------------


@frappe.whitelist()
def create_pi_from_multiple_dns(delivery_note_names):
	"""Create one Draft Purchase Invoice from multiple inter-company DNs."""
	names = _normalise_names(delivery_note_names)
	if not names:
		frappe.throw(_("Select at least one Delivery Note."))

	dns = [frappe.get_doc("Delivery Note", n) for n in names]
	_validate_batch(dns)

	head = dns[0]
	buying_company = head.represents_company
	supplier = _resolve_internal_supplier(head.customer, buying_company)

	pi = frappe.new_doc("Purchase Invoice")
	pi.company = buying_company
	pi.supplier = supplier
	pi.posting_date = frappe.utils.today()
	pi.due_date = frappe.utils.today()
	pi.currency = head.currency
	pi.is_internal_supplier = 1
	pi.represents_company = head.company
	pi.bill_no = ", ".join(dn.name for dn in dns)[:140]
	pi.bill_date = head.posting_date

	# Items — one PI row per DN item, preserving source reference
	for dn in dns:
		for item in dn.items:
			pi.append("items", {
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"qty": item.qty,
				"rate": item.rate,
				"amount": item.amount,
				"uom": item.uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": item.conversion_factor or 1,
				"delivery_note": dn.name,
				"dn_detail": item.name,
			})

	# Taxes — inherit from the first DN
	for tax in (head.taxes or []):
		pi.append("taxes", {
			"charge_type": tax.charge_type,
			"account_head": tax.account_head,
			"description": tax.description,
			"rate": tax.rate,
			"tax_amount": tax.tax_amount,
			"cost_center": tax.cost_center,
			"category": tax.category,
			"add_deduct_tax": tax.add_deduct_tax,
			"included_in_print_rate": tax.included_in_print_rate,
		})

	# Inter Company Branch master lookup → cost center + warehouse
	branch_data = _get_branch_data(head.get("custom_inter_company_branch"), buying_company)
	if branch_data.get("cost_center"):
		pi.cost_center = branch_data["cost_center"]
		for item in pi.items:
			item.cost_center = branch_data["cost_center"]

	if cint(pi.update_stock) and branch_data.get("warehouse"):
		if _warehouse_belongs_to_company(branch_data["warehouse"], buying_company):
			pi.set_warehouse = branch_data["warehouse"]
			for item in pi.items:
				item.warehouse = branch_data["warehouse"]

	pi.insert(ignore_permissions=False)

	# Stamp each source DN
	for dn in dns:
		frappe.db.set_value(
			"Delivery Note",
			dn.name,
			{
				"custom_inter_company_pi": pi.name,
				"custom_inter_company_status": STATUS_CONSOLIDATED,
			},
			update_modified=False,
		)

	frappe.db.commit()
	return pi.name


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def purchase_invoice_on_cancel(doc, method=None):
	"""When a consolidated PI is cancelled, free up the source DNs."""
	linked = frappe.get_all(
		"Delivery Note",
		filters={"custom_inter_company_pi": doc.name},
		pluck="name",
	)
	for name in linked:
		frappe.db.set_value(
			"Delivery Note",
			name,
			{
				"custom_inter_company_pi": None,
				"custom_inter_company_status": STATUS_NOT_CONSOLIDATED,
			},
			update_modified=False,
		)
	if linked:
		frappe.db.commit()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_batch(dns):
	if len(dns) < 1:
		frappe.throw(_("Select at least one Delivery Note."))

	head = dns[0]

	# Each DN must be submitted, flagged as inter-company, and un-consolidated
	for dn in dns:
		if dn.docstatus != 1:
			frappe.throw(_("Delivery Note {0} is not submitted.").format(dn.name))
		if not dn.get("custom_is_inter_company"):
			frappe.throw(
				_("Delivery Note {0} is not marked as Inter Company.").format(dn.name)
			)
		if not dn.get("is_internal_customer"):
			frappe.throw(
				_("Delivery Note {0} is not an internal-customer DN.").format(dn.name)
			)
		if not dn.get("represents_company"):
			frappe.throw(
				_("Delivery Note {0} has no represents_company set.").format(dn.name)
			)
		if dn.get("custom_inter_company_pi"):
			existing_status = frappe.db.get_value(
				"Purchase Invoice", dn.custom_inter_company_pi, "docstatus"
			)
			if existing_status in (0, 1):
				frappe.throw(
					_("Delivery Note {0} is already linked to Purchase Invoice {1}.").format(
						dn.name, dn.custom_inter_company_pi
					)
				)

	# All DNs must agree on buying company, supplier, currency, branch
	checks = {
		"represents_company": head.represents_company,
		"customer": head.customer,
		"currency": head.currency,
		"custom_inter_company_branch": head.get("custom_inter_company_branch"),
	}
	for dn in dns[1:]:
		for field, expected in checks.items():
			if dn.get(field) != expected:
				frappe.throw(
					_("Delivery Note {0} has {1} = {2}; expected {3}.").format(
						dn.name, field, dn.get(field), expected
					)
				)


def _normalise_names(delivery_note_names) -> List[str]:
	if isinstance(delivery_note_names, str):
		import json

		try:
			parsed = json.loads(delivery_note_names)
			if isinstance(parsed, list):
				return [str(n) for n in parsed if n]
			return [str(parsed)]
		except Exception:
			return [delivery_note_names]
	if isinstance(delivery_note_names, list):
		return [str(n) for n in delivery_note_names if n]
	return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_internal_supplier(customer: str, buying_company: str) -> str:
	"""Find the internal Supplier record linked to the selling Company."""
	# Pattern: Customer represents a Company; the matching Supplier in the
	# other Company is flagged is_internal_supplier and has
	# represents_company = selling Company.
	selling_company = frappe.db.get_value("Customer", customer, "represents_company")
	if not selling_company:
		frappe.throw(
			_("Customer {0} has no represents_company — cannot resolve supplier.").format(customer)
		)

	supplier = frappe.db.get_value(
		"Supplier",
		{
			"is_internal_supplier": 1,
			"represents_company": selling_company,
		},
		"name",
	)
	if not supplier:
		# Try by linked Companies list (multi-company supplier)
		supplier = frappe.db.sql(
			"""
			SELECT s.name
			FROM `tabSupplier` s
			JOIN `tabAllowed To Transact With` a ON a.parent = s.name
			WHERE s.is_internal_supplier = 1
			  AND s.represents_company = %s
			  AND a.company = %s
			LIMIT 1
			""",
			(selling_company, buying_company),
		)
		supplier = supplier[0][0] if supplier else None

	if not supplier:
		frappe.throw(
			_("No internal Supplier found for selling Company {0} under buying Company {1}.").format(
				selling_company, buying_company
			)
		)
	return supplier


def _get_branch_data(inter_company_branch: str | None, buying_company: str) -> dict:
	import erpnext

	result = {}
	if inter_company_branch and buying_company:
		row = frappe.db.get_value(
			"Inter Company Branch Cost Center",
			{"parent": inter_company_branch, "company": buying_company},
			["cost_center", "warehouse"],
			as_dict=True,
		)
		if row:
			if row.cost_center:
				result["cost_center"] = row.cost_center
			if row.warehouse:
				result["warehouse"] = row.warehouse

	if "cost_center" not in result:
		result["cost_center"] = erpnext.get_default_cost_center(buying_company)

	return result


def _warehouse_belongs_to_company(warehouse: str, company: str) -> bool:
	if not warehouse or not company:
		return False
	wh_company = frappe.db.get_value("Warehouse", warehouse, "company", cache=True)
	return wh_company == company
