"""Multi-DN consolidated Return — produces a single Sales Invoice with
`is_return=1, update_stock=1` from a batch of submitted Delivery Notes.

Design:
* No auto-creation on individual DN submit. Operator triggers from the
  Delivery Note list action 'Create Return Invoice'.
* All selected DNs must share customer + company + currency + branch
  (the latter so the Phase A return-series picker resolves a single
  series — see Branch.custom_naming_series_table with use_for_return=1).
* Each item row from every selected DN is added to the SI with
  qty negated and `delivery_note=<source>, dn_detail=<row.name>` so
  Frappe's stock-return logic can match the original outgoing entry.
* Each source DN gets `custom_return_si = <SI.name>` stamped on insert.
  Cancelling the SI clears those stamps.
* No SI submit here — operator reviews, edits, and submits manually.
* Bypasses ram_custom-style 'block_inter_company_invoices' guards by
  not flagging the SI as inter-company; this is a vanilla return SI.
"""

from __future__ import annotations

import json
from typing import List

import frappe
from frappe import _
from frappe.utils import flt

from rmax_custom.inter_company_dn import (
    _build_inter_company_si_from_buckets,
    _copy_tax_row,
)


STATUS_NOT_RETURNED = "Not Returned"
STATUS_RETURNED = "Returned"


@frappe.whitelist()
def create_return_si_from_multiple_dns(delivery_note_names) -> str:
    """Create a single Draft Sales Invoice (is_return=1, update_stock=1)
    rolling up every line of every selected Delivery Note.

    Returns the new Sales Invoice name.

    Raises `frappe.ValidationError` on any cross-batch mismatch or when
    a DN is already linked to a non-cancelled return SI.
    """
    names = _normalise_names(delivery_note_names)
    dns = [frappe.get_doc("Delivery Note", n) for n in names]

    _validate_batch(dns)

    head = dns[0]
    si = frappe.new_doc("Sales Invoice")
    si.customer = head.customer
    si.customer_name = head.customer_name
    si.company = head.company
    si.currency = head.currency
    si.posting_date = frappe.utils.today()
    si.set_posting_time = 1
    si.is_return = 1
    si.update_stock = 1
    si.set("taxes", [])
    if head.taxes_and_charges:
        si.taxes_and_charges = head.taxes_and_charges
        # Pull taxes by name to avoid copying with manually-overridden values.
        try:
            template = frappe.get_doc("Sales Taxes and Charges Template", head.taxes_and_charges)
            for t in template.taxes:
                si.append("taxes", {
                    "charge_type": t.charge_type,
                    "account_head": t.account_head,
                    "rate": t.rate,
                    "description": t.description,
                    "cost_center": t.cost_center,
                    "included_in_print_rate": t.included_in_print_rate,
                })
        except Exception:
            # Non-fatal — operator can re-pull taxes via the form.
            frappe.log_error(
                frappe.get_traceback(),
                "rmax_custom: failed to expand taxes template for return SI",
            )

    if head.cost_center:
        si.cost_center = head.cost_center
    if head.set_warehouse:
        si.set_warehouse = head.set_warehouse

    branch = head.get("branch")
    if branch:
        si.branch = branch

    # Build the items list by walking every selected DN's rows.
    for dn in dns:
        for row in dn.items:
            si.append("items", {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "description": row.description,
                "qty": -1 * abs(flt(row.qty)),
                "uom": row.uom,
                "stock_uom": row.stock_uom,
                "conversion_factor": row.conversion_factor,
                "rate": row.rate,
                "amount": -1 * abs(flt(row.amount)),
                "warehouse": row.warehouse,
                "income_account": row.income_account,
                "cost_center": row.cost_center,
                "delivery_note": dn.name,
                "dn_detail": row.name,
            })

    si.flags.ignore_permissions = False
    si.insert(ignore_permissions=False)

    # Stamp the source DNs with the new SI name.
    for dn in dns:
        frappe.db.set_value(
            "Delivery Note",
            dn.name,
            {
                "custom_return_si": si.name,
            },
            update_modified=False,
        )

    frappe.db.commit()
    return si.name


def sales_invoice_on_cancel_clear_dn_return(doc, method=None) -> None:
    """When a return SI is cancelled, clear the `custom_return_si`
    backlink on every DN that pointed at it so the DNs become eligible
    for a fresh return run.
    """
    if not doc.get("is_return"):
        return
    dns = frappe.get_all(
        "Delivery Note",
        filters={"custom_return_si": doc.name},
        pluck="name",
    )
    for n in dns:
        frappe.db.set_value(
            "Delivery Note",
            n,
            {"custom_return_si": None},
            update_modified=False,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_names(delivery_note_names) -> List[str]:
    if not delivery_note_names:
        frappe.throw(_("Please select at least one Delivery Note."))
    if isinstance(delivery_note_names, str):
        try:
            delivery_note_names = json.loads(delivery_note_names)
        except (TypeError, ValueError):
            delivery_note_names = [delivery_note_names]
    if not isinstance(delivery_note_names, (list, tuple)):
        frappe.throw(_("delivery_note_names must be a list of names."))
    names = [str(n).strip() for n in delivery_note_names if str(n).strip()]
    if not names:
        frappe.throw(_("Please select at least one Delivery Note."))
    return list(dict.fromkeys(names))  # dedupe preserving order


def _validate_batch(dns: List["frappe.model.document.Document"]) -> None:
    if not dns:
        frappe.throw(_("No Delivery Notes resolved."))

    head = dns[0]

    if not frappe.has_permission("Delivery Note", "read", doc=head.name):
        frappe.throw(_("You do not have permission to read Delivery Note {0}.").format(head.name))

    for dn in dns:
        if dn.docstatus != 1:
            frappe.throw(_("Delivery Note {0} is not submitted.").format(dn.name))
        if dn.is_return:
            frappe.throw(_("Delivery Note {0} is itself a return — not eligible.").format(dn.name))
        if dn.customer != head.customer:
            frappe.throw(_("All selected Delivery Notes must share the same customer."))
        if dn.company != head.company:
            frappe.throw(_("All selected Delivery Notes must share the same company."))
        if dn.currency != head.currency:
            frappe.throw(_("All selected Delivery Notes must share the same currency."))
        if (dn.get("branch") or "") != (head.get("branch") or ""):
            frappe.throw(_("All selected Delivery Notes must share the same branch."))

        existing_si = dn.get("custom_return_si")
        if existing_si and frappe.db.exists("Sales Invoice", existing_si):
            si_status = frappe.db.get_value("Sales Invoice", existing_si, "docstatus")
            if si_status != 2:
                frappe.throw(
                    _(
                        "Delivery Note {0} is already linked to a non-cancelled "
                        "return Sales Invoice {1}. Cancel that SI first."
                    ).format(dn.name, existing_si)
                )


# ---------------------------------------------------------------------------
# Mixed DN + Return DN consolidation — net-off by (item_code, uom)
# ---------------------------------------------------------------------------


def _normalise_consolidation_names(delivery_note_names):
    if isinstance(delivery_note_names, str):
        delivery_note_names = json.loads(delivery_note_names)
    if not delivery_note_names:
        frappe.throw(_("Select at least one Delivery Note"))
    return delivery_note_names


def _validate_consolidation_batch(dns):
    if any(d.docstatus != 1 for d in dns):
        frappe.throw(_("All Delivery Notes must be submitted"))

    for d in dns:
        existing = d.get("custom_consolidated_si")
        if existing and frappe.db.exists(
            "Sales Invoice", {"name": existing, "docstatus": ["!=", 2]}
        ):
            frappe.throw(_(
                "DN {0} already linked to non-cancelled Sales Invoice {1}"
            ).format(d.name, existing))

    keys = ["customer", "company", "currency"]
    first = {k: dns[0].get(k) for k in keys}
    for d in dns[1:]:
        for k in keys:
            if d.get(k) != first[k]:
                frappe.throw(_(
                    "DN {0} mismatched on {1}: expected {2}, got {3}"
                ).format(d.name, k, first[k], d.get(k)))


def _net_items_across_dns(dns):
    """Bucket rows by (item_code, uom). Return DNs subtract."""
    buckets = {}
    for dn in dns:
        sign = -1 if dn.is_return else 1
        for row in dn.items:
            key = (row.item_code, row.uom)
            b = buckets.setdefault(key, {
                "qty": 0, "amount": 0, "uom": row.uom, "src_rows": [],
            })
            qty = sign * abs(flt(row.qty or 0))
            amount = sign * abs(flt(row.amount or (row.qty * row.rate) or 0))
            b["qty"] += qty
            b["amount"] += amount
            b["src_rows"].append({"dn": dn.name, "row": row.name})
    return buckets


def _build_consolidated_standard_si(dns, buckets):
    head = dns[0]
    si = frappe.new_doc("Sales Invoice")
    si.customer = head.customer
    si.customer_name = head.customer_name
    si.company = head.company
    si.currency = head.currency
    si.posting_date = frappe.utils.today()
    si.set_posting_time = 1
    si.update_stock = 0
    if head.set_warehouse:
        si.set_warehouse = head.set_warehouse
    if head.get("branch"):
        si.branch = head.get("branch")

    # Inherit taxes from first non-return DN.
    for dn in dns:
        if not dn.is_return and dn.taxes_and_charges:
            si.taxes_and_charges = dn.taxes_and_charges
            for t in dn.taxes:
                si.append("taxes", _copy_tax_row(t))
            break

    for (item_code, uom), b in buckets.items():
        if b["qty"] <= 0:
            continue
        rate = (b["amount"] / b["qty"]) if b["qty"] else 0
        src = b["src_rows"][0]
        si.append("items", {
            "item_code": item_code,
            "qty": b["qty"],
            "uom": uom,
            "rate": rate,
            "delivery_note": src["dn"],
            "dn_detail": src["row"],
        })

    return si


@frappe.whitelist()
def consolidate_dns_to_si(delivery_note_names):
    """Mixed DN + Return DN consolidation into a single Draft Sales Invoice
    with net-off by (item_code, uom)."""
    names = _normalise_consolidation_names(delivery_note_names)
    dns = [frappe.get_doc("Delivery Note", n) for n in names]

    _validate_consolidation_batch(dns)
    buckets = _net_items_across_dns(dns)

    is_inter_company = bool(dns[0].get("custom_is_inter_company"))
    if is_inter_company:
        # All rows must agree.
        if any(not d.get("custom_is_inter_company") for d in dns):
            frappe.throw(_("Cannot mix inter-company and standard DNs in one batch"))
        si = _build_inter_company_si_from_buckets(dns, buckets)
    else:
        si = _build_consolidated_standard_si(dns, buckets)

    if not si.items:
        frappe.throw(_(
            "After netting returns, no item has positive qty. "
            "Sales Invoice not created."
        ))

    si.insert(ignore_permissions=False)

    for dn in dns:
        frappe.db.set_value(
            "Delivery Note", dn.name,
            "custom_consolidated_si", si.name,
            update_modified=False,
        )

    return si.name
