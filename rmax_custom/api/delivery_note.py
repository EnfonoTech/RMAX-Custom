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
