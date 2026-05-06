# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""Inter-Company Delivery Note → consolidated Sales Invoice.

Operators pick multiple submitted inter-company Delivery Notes and roll
them up into a single Draft Sales Invoice issued by the SELLING company
(Head Office). The existing `inter_company.py::sales_invoice_on_submit`
hook then creates the matching Purchase Invoice on the receiving side
once an accountant submits the SI.

Design:
* No auto-create on DN submit — consolidation is always explicit via
  the list action (per client requirement).
* Validation: every selected DN must be submitted, flagged inter
  company (custom_is_inter_company=1), share customer, represents_
  company, currency, custom_inter_company_branch, and not already be
  linked to another non-cancelled SI.
* Output SI inherits taxes from the first selected DN; cost center and
  warehouse come from the Inter Company Branch master entry that
  matches the selling Company.
* Each source DN is stamped with custom_inter_company_si and
  custom_inter_company_status = "Consolidated". Cancelling the SI
  clears those stamps so the DNs can be rolled into a different SI.
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
	_cleanup_legacy_pi_field()
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


def _cleanup_legacy_pi_field():
	"""Drop the obsolete custom_inter_company_pi Custom Field on Delivery Note.

	That field was introduced for a Purchase-Invoice-based flow which
	has since been replaced by custom_inter_company_si. Removal is
	idempotent and safe — no migrations reference the old name.
	"""
	legacy = "Delivery Note-custom_inter_company_pi"
	if not frappe.db.exists("Custom Field", legacy):
		return
	try:
		frappe.delete_doc("Custom Field", legacy, ignore_permissions=True, force=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"rmax_custom: failed to delete legacy custom_inter_company_pi field",
		)


# ---------------------------------------------------------------------------
# SI-building helpers — shared by all consolidation paths
# ---------------------------------------------------------------------------


def _build_positive_only_buckets(dns):
	"""Build buckets without netting — every row sign=+1.

	Used by the existing inter-company SI consolidation flow which assumes
	all selected DNs are positive (no return DNs in the batch).

	Returns a dict keyed by ``(item_code, uom)`` where each value holds:
	  - ``qty``      — accumulated absolute qty
	  - ``amount``   — accumulated absolute amount (qty * rate)
	  - ``uom``      — UOM string (mirrors the key component)
	  - ``src_rows`` — list of ``{"dn": dn.name, "row": row.name, "item": row}``
	                   preserving all per-row attributes for the first-row copy
	"""
	buckets = {}
	for dn in dns:
		for row in dn.items:
			key = (row.item_code, row.uom)
			b = buckets.setdefault(key, {
				"qty": 0, "amount": 0, "uom": row.uom, "src_rows": [],
			})
			b["qty"] += flt(abs(row.qty or 0))
			b["amount"] += flt(abs(row.amount or ((row.qty or 0) * (row.rate or 0))))
			b["src_rows"].append({"dn": dn.name, "row": row.name, "item": row})
	return buckets


def _copy_tax_row(t):
	"""Return a dict suitable for ``si.append("taxes", ...)`` from a DN tax row."""
	return {
		"charge_type": t.charge_type,
		"account_head": t.account_head,
		"description": t.description,
		"rate": t.rate,
		"tax_amount": t.tax_amount,
		"cost_center": t.cost_center,
		"included_in_print_rate": t.included_in_print_rate,
	}


def _build_inter_company_si_from_buckets(dns, buckets):
	"""Build an inter-company Draft Sales Invoice from pre-netted buckets.

	Used by both the all-positive path (``create_si_from_multiple_dns``) and
	the new mixed-net path (``api.delivery_note.consolidate_dns_to_si``).

	The caller is responsible for:
	- setting ``si.set_target_warehouse`` + per-item ``target_warehouse``
	- calling ``si.insert()``

	Field resolution follows the SELLING-company (head.company) convention
	used throughout this module — ``head.company`` is the selling side, not
	``head.represents_company`` (which is the buying company).
	"""
	head = dns[0]
	selling_company = head.company

	si = frappe.new_doc("Sales Invoice")
	si.company = selling_company
	si.customer = head.customer
	si.is_internal_customer = 1
	si.represents_company = head.represents_company
	si.posting_date = frappe.utils.today()
	si.due_date = frappe.utils.today()
	si.currency = head.currency
	si.selling_price_list = head.selling_price_list or INTER_COMPANY_PRICE_LIST
	# DNs already moved stock on the selling side. SI is invoice-only.
	si.update_stock = 0
	if head.get("custom_inter_company_branch"):
		si.custom_inter_company_branch = head.custom_inter_company_branch

	# Items — one SI row per consolidated bucket
	for (item_code, uom), b in buckets.items():
		if flt(b["qty"]) <= 0:
			continue
		rate = flt(b["amount"]) / flt(b["qty"]) if flt(b["qty"]) else 0
		src = b["src_rows"][0]
		src_item = src["item"]  # original DN item row for attribute copying
		si.append("items", {
			"item_code": item_code,
			"item_name": src_item.item_name,
			"description": src_item.description,
			"qty": b["qty"],
			"rate": rate,
			"uom": uom,
			"stock_uom": src_item.stock_uom,
			"conversion_factor": src_item.conversion_factor or 1,
			"warehouse": src_item.warehouse,
			"delivery_note": src["dn"],
			"dn_detail": src["row"],
		})

	# Taxes — inherit from the first DN
	for tax in (head.taxes or []):
		si.append("taxes", _copy_tax_row(tax))

	# Inter Company Branch master lookup → cost center for the SELLING side.
	branch = head.get("custom_inter_company_branch")
	branch_data = _get_branch_data(branch, selling_company)
	if branch_data.get("cost_center"):
		si.cost_center = branch_data["cost_center"]
		for item in si.items:
			item.cost_center = branch_data["cost_center"]

	return si


# ---------------------------------------------------------------------------
# Whitelisted API — called from Delivery Note list action
# ---------------------------------------------------------------------------


@frappe.whitelist()
def create_si_from_multiple_dns(delivery_note_names):
	"""Create one Draft Sales Invoice from multiple inter-company DNs."""
	names = _normalise_names(delivery_note_names)
	if not names:
		frappe.throw(_("Select at least one Delivery Note."))

	dns = [frappe.get_doc("Delivery Note", n) for n in names]
	_validate_batch(dns)

	buckets = _build_positive_only_buckets(dns)
	si = _build_inter_company_si_from_buckets(dns, buckets)

	# Internal-customer SIs require a target warehouse on every row — that's the
	# BUYING-company warehouse which receives the auto-generated PI's stock.
	# Fetch it from the buying-company row of the same Inter Company Branch.
	head = dns[0]
	branch = head.get("custom_inter_company_branch")
	target_warehouse = _get_target_warehouse(branch, head.represents_company)
	if not target_warehouse:
		frappe.throw(
			_("Configure a Warehouse for company {0} on Inter Company Branch {1} before consolidating.").format(
				frappe.bold(head.represents_company),
				frappe.bold(branch or "—"),
			),
			title=_("Target Warehouse Missing"),
		)
	si.set_target_warehouse = target_warehouse
	for item in si.items:
		item.target_warehouse = target_warehouse

	si.insert(ignore_permissions=False)

	# Stamp each source DN
	for dn in dns:
		frappe.db.set_value(
			"Delivery Note",
			dn.name,
			{
				"custom_inter_company_si": si.name,
				"custom_inter_company_status": STATUS_CONSOLIDATED,
			},
			update_modified=False,
		)

	frappe.db.commit()
	return si.name


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def sales_invoice_on_submit(doc, method=None):
	"""When a consolidated inter-company SI is submitted, refresh
	billing status on each source DN so the list view shows
	'Completed'/'Billed' instead of 'To Bill'.
	"""
	dn_names = _source_dns_for_si(doc)
	if not dn_names:
		return
	_refresh_dn_billing_status(dn_names)


def sales_invoice_on_cancel(doc, method=None):
	"""When a consolidated SI is cancelled, free up the source DNs and
	reset their billing status."""
	linked = frappe.get_all(
		"Delivery Note",
		filters={"custom_inter_company_si": doc.name},
		pluck="name",
	)
	# Source DN names from item references — include any DN linked via
	# delivery_note even if it didn't get the custom stamp.
	dn_names = list(set(linked) | _source_dns_for_si(doc))

	for name in linked:
		frappe.db.set_value(
			"Delivery Note",
			name,
			{
				"custom_inter_company_si": None,
				"custom_inter_company_status": STATUS_NOT_CONSOLIDATED,
			},
			update_modified=False,
		)
	if dn_names:
		_refresh_dn_billing_status(dn_names)
	if linked:
		frappe.db.commit()

	# Clear the net-off consolidation stamp on every DN linked via
	# custom_consolidated_si. (Set by api.delivery_note.consolidate_dns_to_si.)
	consolidated_dns = frappe.get_all(
		"Delivery Note",
		filters={"custom_consolidated_si": doc.name},
		pluck="name",
	)
	for dn_name in consolidated_dns:
		frappe.db.set_value(
			"Delivery Note", dn_name,
			"custom_consolidated_si", None,
			update_modified=False,
		)


def _source_dns_for_si(si_doc) -> set[str]:
	names: set[str] = set()
	for row in (si_doc.get("items") or []):
		ref = (getattr(row, "delivery_note", None) or "").strip()
		if ref:
			names.add(ref)
	return names


def _refresh_dn_billing_status(dn_names):
	"""Recompute per_billed + status on each DN.

	Re-runs ERPNext's standard billing-status calculation for each DN by
	loading the doc and calling `update_billing_status`. That writes
	`per_billed` and the derived `status` (Completed / To Bill / etc.).
	"""
	for name in dn_names:
		try:
			dn = frappe.get_doc("Delivery Note", name)
			# `update_billing_status` is on the SellingController parent.
			# It iterates DN items, sums billed amount from linked SI rows,
			# updates per_billed, and stamps status.
			dn.update_billing_status(update_modified=False)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"rmax_custom: DN billing status refresh failed for {name}",
			)


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
		if dn.get("custom_inter_company_si"):
			existing_status = frappe.db.get_value(
				"Sales Invoice", dn.custom_inter_company_si, "docstatus"
			)
			if existing_status in (0, 1):
				frappe.throw(
					_("Delivery Note {0} is already linked to Sales Invoice {1}.").format(
						dn.name, dn.custom_inter_company_si
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


def _get_target_warehouse(inter_company_branch: str | None, buying_company: str | None) -> str | None:
	"""Return the buying-side warehouse from Inter Company Branch Cost Center."""
	if not inter_company_branch or not buying_company:
		return None
	return frappe.db.get_value(
		"Inter Company Branch Cost Center",
		{"parent": inter_company_branch, "company": buying_company},
		"warehouse",
	)


def _warehouse_belongs_to_company(warehouse: str, company: str) -> bool:
	if not warehouse or not company:
		return False
	wh_company = frappe.db.get_value("Warehouse", warehouse, "company", cache=True)
	return wh_company == company
