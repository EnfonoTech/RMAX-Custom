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
from frappe.utils import cstr, flt

from rmax_custom.inter_company_dn import (
    _build_inter_company_si_from_buckets,
    _copy_tax_row,
)


STATUS_NOT_RETURNED = "Not Returned"
STATUS_RETURNED = "Returned"


# ---------------------------------------------------------------------------
# DN Return — Source DN Lookup
# ---------------------------------------------------------------------------


@frappe.whitelist()
def find_source_delivery_notes(customer: str, items) -> list:
    """Given a customer and a list of items being returned, find submitted
    Delivery Notes that contain those items with remaining returnable qty.

    Returns a list of candidate DNs ranked by match score (most items
    matched first), then by posting_date descending (most recent first).

    Args:
        customer: Customer name (Link field value)
        items: JSON list of {"item_code": str, "qty": float}

    Returns:
        [
          {
            "name": "DN-0001",
            "posting_date": "2026-05-01",
            "score": 3,            # how many of the requested items were found
            "items": [
              {
                "item_code": "ITEM-001",
                "item_name": "...",
                "qty": 10.0,
                "returned_qty": 2.0,
                "returnable_qty": 8.0,
                "uom": "Nos",
                "rate": 100.0,
                "warehouse": "Main Warehouse - RMAX",
              },
              ...
            ]
          },
          ...
        ]
    """
    frappe.has_permission("Delivery Note", ptype="read", throw=True)

    if not customer:
        frappe.throw(_("customer is required"))

    if isinstance(items, str):
        items = frappe.parse_json(items)

    if not items:
        frappe.throw(_("At least one item is required"))

    item_codes = list({cstr(i.get("item_code")) for i in items if i.get("item_code")})
    if not item_codes:
        frappe.throw(_("No valid item codes provided"))

    # Single parameterised query — no string interpolation
    rows = frappe.db.sql(
        """
        SELECT
            dn.name,
            dn.posting_date,
            dn.customer,
            dni.item_code,
            dni.item_name,
            dni.qty,
            COALESCE(dni.returned_qty, 0) AS returned_qty,
            dni.uom,
            dni.rate,
            dni.warehouse
        FROM `tabDelivery Note` dn
        INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
        WHERE
            dn.docstatus = 1
            AND dn.is_return = 0
            AND dn.customer = %s
            AND dni.item_code IN %s
            AND (dni.qty - COALESCE(dni.returned_qty, 0)) > 0
        ORDER BY dn.posting_date DESC, dn.name DESC
        """,
        (customer, tuple(item_codes)),
        as_dict=True,
    )

    # Group by DN name, build result structure
    dn_map: dict = {}
    for r in rows:
        if r.name not in dn_map:
            dn_map[r.name] = {
                "name": r.name,
                "posting_date": str(r.posting_date),
                "score": 0,
                "items": [],
            }
        returnable = flt(r.qty) - flt(r.returned_qty)
        dn_map[r.name]["items"].append(
            {
                "item_code": r.item_code,
                "item_name": r.item_name,
                "qty": flt(r.qty),
                "returned_qty": flt(r.returned_qty),
                "returnable_qty": returnable,
                "uom": r.uom,
                "rate": flt(r.rate),
                "warehouse": r.warehouse,
            }
        )
        dn_map[r.name]["score"] += 1

    # Sort: most matched items first, then most recent date
    results = sorted(
        dn_map.values(),
        key=lambda d: (-d["score"], d["posting_date"]),
    )
    return results


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
    # NOTE: do NOT set `delivery_note` / `dn_detail` on item rows. ERPNext's
    # `validate_delivery_note` (sales_invoice.py:1046) throws
    # "Stock cannot be updated against Delivery Note ..." when update_stock=1
    # AND any item carries a delivery_note link — it prevents double stock
    # movement (the source DN already moved stock; this Return SI reverses
    # it via its own Stock Ledger Entries). Reverse traceability lives on
    # `DN.custom_return_si` stamp set below.
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
                "cost_center": row.cost_center,
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
                "qty": 0, "amount": 0, "uom": row.uom,
                "warehouse": row.get("warehouse") or dn.get("set_warehouse"),
                "src_rows": [],
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

    # Resolve branch for GL accounting dimension — prefer explicit DN branch,
    # then fall back to warehouse → branch mapping from Branch Configuration.
    if head.get("branch"):
        si.branch = head.get("branch")
    elif head.set_warehouse:
        try:
            from rmax_custom.inter_branch import resolve_warehouse_branch
            resolved = resolve_warehouse_branch(head.set_warehouse)
            if resolved:
                si.branch = resolved
        except Exception:
            pass

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
        # Do not set delivery_note/dn_detail — netted qty cannot be attributed
        # to a single DN row and would trigger validate_multiple_billing.
        # DN linkage is tracked via custom_consolidated_si on each DN instead.
        # Warehouse is set so auto_set_branch_from_warehouse can resolve the
        # Branch accounting dimension required by the site.
        si.append("items", {
            "item_code": item_code,
            "qty": b["qty"],
            "uom": uom,
            "rate": rate,
            "warehouse": b.get("warehouse"),
        })

    return si


@frappe.whitelist()
def create_consolidated_return_dn_from_dns(delivery_note_names) -> str:
    """Build a single Draft Return Delivery Note (is_return=1) consolidating
    rows from multiple submitted source DNs. Stock reverses via SLE on submit.

    Per ERPNext convention, Return DN with empty `return_against` is permitted
    (validate_return early-returns at sales_and_purchase_return.py:21 when
    `doc.return_against` is falsy). This skips per-row validate_returned_items,
    so we replace it with our own batch-level guard.

    Returns the new Return DN name.

    Raises frappe.ValidationError on:
    - any DN not submitted
    - source DN is itself a return
    - cross-DN customer/company/currency mismatch
    - DN already linked to a non-cancelled Return DN
    """
    names = _normalise_consolidation_names(delivery_note_names)
    dns = [frappe.get_doc("Delivery Note", n) for n in names]

    _validate_return_dn_batch(dns)

    head = dns[0]
    rdn = frappe.new_doc("Delivery Note")
    rdn.customer = head.customer
    rdn.customer_name = head.customer_name
    rdn.company = head.company
    rdn.currency = head.currency
    rdn.posting_date = frappe.utils.today()
    rdn.set_posting_time = 1
    rdn.is_return = 1
    rdn.return_against = ""  # intentionally empty — validate_return early-exits when falsy

    if head.get("branch"):
        rdn.branch = head.get("branch")
    if head.set_warehouse:
        rdn.set_warehouse = head.set_warehouse

    # Inherit taxes from first DN that has a tax template
    for dn in dns:
        if dn.taxes_and_charges:
            rdn.taxes_and_charges = dn.taxes_and_charges
            for t in dn.taxes:
                rdn.append("taxes", _copy_dn_tax_row(t))
            break

    for dn in dns:
        for row in dn.items:
            # NOTE: dn_detail, against_sales_order, so_detail are intentionally
            # NOT set. ERPNext's status_updater for is_return DNs uses dn_detail
            # (join_field) with percent_join_field_parent="return_against" to
            # update per_returned on the source DN. Since return_against is empty
            # (our loophole), the updater resolves an empty DN name and throws
            # DoesNotExistError. Traceability is provided by custom_return_dn
            # stamp on the source DN instead.
            rdn.append("items", {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "description": row.description,
                "qty": -1 * abs(flt(row.qty)),
                "uom": row.uom,
                "stock_uom": row.stock_uom,
                "conversion_factor": row.conversion_factor,
                "rate": row.rate,
                "incoming_rate": row.rate,  # preserve valuation for SLE
                "warehouse": row.warehouse,
                "cost_center": row.cost_center,
                "expense_account": row.get("expense_account"),
            })

    rdn.insert(ignore_permissions=False)

    # Stamp source DNs with the new Return DN name
    for dn in dns:
        frappe.db.set_value(
            "Delivery Note", dn.name,
            "custom_return_dn", rdn.name,
            update_modified=False,
        )

    return rdn.name


def _validate_return_dn_batch(dns):
    """Pre-validation for create_consolidated_return_dn_from_dns."""
    if not dns:
        frappe.throw(_("No Delivery Notes resolved."))

    if any(d.docstatus != 1 for d in dns):
        frappe.throw(_("All Delivery Notes must be submitted."))

    if any(d.is_return for d in dns):
        frappe.throw(_("Cannot create Return DN from Return Delivery Notes."))

    for d in dns:
        existing = d.get("custom_return_dn")
        if existing and frappe.db.exists(
            "Delivery Note", {"name": existing, "docstatus": ["!=", 2]}
        ):
            frappe.throw(_(
                "DN {0} already linked to non-cancelled Return DN {1}."
            ).format(d.name, existing))

    keys = ["customer", "company", "currency"]
    first = {k: dns[0].get(k) for k in keys}
    for d in dns[1:]:
        for k in keys:
            if d.get(k) != first[k]:
                frappe.throw(_(
                    "DN {0} mismatched on {1}: expected {2}, got {3}."
                ).format(d.name, k, first[k], d.get(k)))


def _copy_dn_tax_row(t):
    """Copy a DN tax row for the return DN (negate tax_amount)."""
    return {
        "charge_type": t.charge_type,
        "account_head": t.account_head,
        "rate": t.rate,
        "tax_amount": -1 * flt(t.tax_amount),
        "description": t.description,
        "cost_center": t.cost_center,
        "included_in_print_rate": t.included_in_print_rate,
    }


def before_submit_return_dn_guard(doc, method=None):
    """Hook: Delivery Note before_submit.

    When a consolidated Return DN (is_return=1, return_against='') is about to
    be submitted, strip the is_return status_updater rules that use
    percent_join_field_parent='return_against'. Without return_against set,
    ERPNext's status_updater tries to load `frappe.get_doc("Delivery Note", "")`
    which raises DoesNotExistError.

    The rules stripped are:
    - DN Item → Sales Order Item returned_qty (via so_detail, no issue — no rows)
    - DN Item → Delivery Note Item returned_qty (via dn_detail, uses
      percent_join_field_parent='return_against' → triggers empty-name load)

    Traceability for our Return DN is handled by the custom_return_dn stamp,
    not ERPNext's per_returned/returned_qty fields.
    """
    if not (doc.is_return and not doc.return_against):
        return
    # Filter out rules whose percent_join_field_parent resolves to empty string
    doc.status_updater = [
        rule for rule in doc.status_updater
        if not (
            rule.get("percent_join_field_parent") == "return_against"
        )
    ]


def clear_consolidated_return_dn_stamp(doc, method=None):
    """Hook: Delivery Note on_cancel.

    When a consolidated Return DN (is_return=1, custom_return_dn stamped on
    sources) is cancelled, clear the stamp on every source DN so they become
    eligible for a new return batch.

    Also covers cancellation of non-return DNs that were erroneously stamped
    (defensive: no-ops on non-return docs quickly).
    """
    if not doc.is_return:
        return
    linked_dns = frappe.get_all(
        "Delivery Note",
        filters={"custom_return_dn": doc.name},
        pluck="name",
    )
    for dn_name in linked_dns:
        frappe.db.set_value(
            "Delivery Note", dn_name,
            "custom_return_dn", None,
            update_modified=False,
        )


def _DEPRECATED_create_return_si_from_multiple_dns(delivery_note_names):
    """DEPRECATED — kept for reference only.

    The original implementation attempted to create a Return SI with
    update_stock=1 + DN item linkage (delivery_note / dn_detail). ERPNext's
    validate_delivery_note (sales_invoice.py) rejects this combination with
    "Stock cannot be updated against Delivery Note ...".

    Use create_consolidated_return_dn_from_dns instead (builds a Return DN that
    reverses stock via SLE). Then run consolidate_dns_to_si on the full set of
    source DNs + the Return DN to produce a net-qty Sales Invoice.

    This function is intentionally not registered as @frappe.whitelist and is
    not wired in any list action.
    """
    return create_return_si_from_multiple_dns(delivery_note_names)


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


# ---------------------------------------------------------------------------
# Multi-source return allocation APIs
# ---------------------------------------------------------------------------

@frappe.whitelist()
def create_bulk_delivery_return(delivery_note_names):
	"""Create a draft Delivery Return from multiple selected Delivery Notes.
	All DNs must share the same customer and company.
	Items are pre-filled with their full returnable qty per source DN.
	Returns the created Delivery Return name.
	"""
	if isinstance(delivery_note_names, str):
		delivery_note_names = json.loads(delivery_note_names)

	if not delivery_note_names:
		frappe.throw(_("No Delivery Notes selected"))

	dns = [frappe.get_doc("Delivery Note", n) for n in delivery_note_names]

	for dn in dns:
		if dn.docstatus != 1:
			frappe.throw(_("{0} is not submitted").format(dn.name))
		if dn.is_return:
			frappe.throw(_("{0} is itself a return — cannot return a return").format(dn.name))

	customers = {dn.customer for dn in dns}
	companies  = {dn.company  for dn in dns}
	if len(customers) > 1:
		frappe.throw(_("All selected Delivery Notes must belong to the same Customer"))
	if len(companies) > 1:
		frappe.throw(_("All selected Delivery Notes must belong to the same Company"))

	customer = dns[0].customer
	company  = dns[0].company

	# Pre-compute already-returned qty per (source_dn, item_code)
	source_dns  = [dn.name for dn in dns]
	item_codes  = list({r.item_code for dn in dns for r in dn.items})

	ret_rows = frappe.db.sql("""
		SELECT
			ret.return_against  AS source_dn,
			reti.item_code,
			SUM(ABS(reti.qty))  AS returned_qty
		FROM `tabDelivery Note` ret
		JOIN `tabDelivery Note Item` reti ON reti.parent = ret.name
		WHERE ret.return_against IN %(source_dns)s
		  AND ret.docstatus      IN (0, 1)
		  AND reti.item_code     IN %(item_codes)s
		GROUP BY ret.return_against, reti.item_code
	""", {"source_dns": source_dns, "item_codes": item_codes}, as_dict=True)

	returned_map = {(r.source_dn, r.item_code): flt(r.returned_qty) for r in ret_rows}

	dr = frappe.new_doc("Delivery Return")
	dr.customer     = customer
	dr.company      = company
	dr.posting_date = frappe.utils.today()

	for dn in dns:
		for item in dn.items:
			returnable = flt(item.qty) - returned_map.get((dn.name, item.item_code), 0)
			if returnable <= 0:
				continue
			dr.append("items", {
				"item_code":              item.item_code,
				"item_name":              item.item_name,
				"against_delivery_note":  dn.name,
				"qty":                    returnable,
				"uom":                    item.uom,
				"rate":                   flt(item.rate),
				"amount":                 returnable * flt(item.rate),
				"returnable_qty":         returnable,
				"warehouse":              item.warehouse,
			})

	if not dr.items:
		frappe.throw(_("No returnable items found in the selected Delivery Notes"))

	dr.insert(ignore_permissions=True)
	return dr.name


@frappe.whitelist()
def get_return_source_dn(customer, company, item_code, qty=1):
	"""Find the most recent (LIFO) source DN for a single item.
	Called by the Delivery Return Request item table to auto-fill Against DN.
	Returns {dn, rate, uom, returnable_qty} or None.
	"""
	qty = flt(qty) or 1

	rows = frappe.db.sql("""
		SELECT
			dn.name          AS dn_name,
			dn.posting_date,
			SUM(dni.qty)     AS total_qty,
			MAX(dni.rate)    AS rate,
			MAX(dni.uom)     AS uom
		FROM `tabDelivery Note` dn
		JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		WHERE dn.customer   = %(customer)s
		  AND dn.company    = %(company)s
		  AND dn.docstatus  = 1
		  AND dn.is_return  = 0
		  AND dni.item_code = %(item_code)s
		GROUP BY dn.name
		ORDER BY dn.posting_date DESC, dn.creation DESC
	""", {"customer": customer, "company": company, "item_code": item_code}, as_dict=True)

	if not rows:
		return None

	source_dns = [r.dn_name for r in rows]
	ret_rows = frappe.db.sql("""
		SELECT ret.return_against AS source_dn, SUM(ABS(reti.qty)) AS returned_qty
		FROM `tabDelivery Note` ret
		JOIN `tabDelivery Note Item` reti ON reti.parent = ret.name
		WHERE ret.return_against IN %(source_dns)s
		  AND ret.docstatus IN (0, 1)
		  AND reti.item_code = %(item_code)s
		GROUP BY ret.return_against
	""", {"source_dns": source_dns, "item_code": item_code}, as_dict=True)

	returned_map = {r.source_dn: flt(r.returned_qty) for r in ret_rows}

	for r in rows:
		returnable = flt(r.total_qty) - returned_map.get(r.dn_name, 0)
		if returnable > 0:
			return {
				"dn": r.dn_name,
				"rate": flt(r.rate),
				"uom": r.uom or "Nos",
				"returnable_qty": flt(returnable, 3),
			}

	return None


@frappe.whitelist()
def resolve_return_allocation(customer, company, items):
    """LIFO allocation — given customer + items, find which submitted DNs they
    came from and group the return quantities by source DN.

    items: JSON list [{item_code, qty}]
    Returns: [{dn, posting_date, items:[{item_code, qty, rate, uom}]}]
    """
    if isinstance(items, str):
        items = json.loads(items)

    item_codes = list({r["item_code"] for r in items if r.get("item_code")})
    if not item_codes:
        frappe.throw(_("No items provided"))

    # All submitted non-return DNs for this customer containing these items
    rows = frappe.db.sql("""
        SELECT
            dn.name          AS dn_name,
            dn.posting_date,
            dni.item_code,
            SUM(dni.qty)     AS total_qty,
            MAX(dni.rate)    AS rate,
            MAX(dni.uom)     AS uom
        FROM `tabDelivery Note` dn
        JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
        WHERE dn.customer  = %(customer)s
          AND dn.company   = %(company)s
          AND dn.docstatus = 1
          AND dn.is_return = 0
          AND dni.item_code IN %(item_codes)s
        GROUP BY dn.name, dni.item_code
        ORDER BY dn.posting_date DESC, dn.creation DESC
    """, {"customer": customer, "company": company, "item_codes": item_codes}, as_dict=True)

    if not rows:
        frappe.throw(_("No delivery notes found for customer {0} with the specified items").format(customer))

    source_dns = list({r.dn_name for r in rows})

    # Already returned qty per (source_dn, item_code) — draft + submitted
    ret_rows = frappe.db.sql("""
        SELECT
            ret.return_against  AS source_dn,
            reti.item_code,
            SUM(ABS(reti.qty))  AS returned_qty
        FROM `tabDelivery Note` ret
        JOIN `tabDelivery Note Item` reti ON reti.parent = ret.name
        WHERE ret.return_against IN %(source_dns)s
          AND ret.docstatus       IN (0, 1)
          AND reti.item_code      IN %(item_codes)s
        GROUP BY ret.return_against, reti.item_code
    """, {"source_dns": source_dns, "item_codes": item_codes}, as_dict=True)

    returned_map = {(r.source_dn, r.item_code): flt(r.returned_qty) for r in ret_rows}

    # Build per-DN available stock: {dn_name: {posting_date, items: {item_code: {returnable_qty, rate, uom}}}}
    dn_info = {}
    for r in rows:
        if r.dn_name not in dn_info:
            dn_info[r.dn_name] = {"posting_date": str(r.posting_date), "items": {}}
        returnable = flt(r.total_qty) - returned_map.get((r.dn_name, r.item_code), 0)
        if returnable > 0:
            dn_info[r.dn_name]["items"][r.item_code] = {
                "returnable_qty": returnable,
                "rate": flt(r.rate),
                "uom": r.uom or "Nos",
            }

    # LIFO: most-recent DN first
    sorted_dns = sorted(dn_info, key=lambda d: dn_info[d]["posting_date"], reverse=True)

    allocations = {}  # {dn_name: {item_code: qty}}

    for item_row in items:
        item_code = item_row.get("item_code")
        if not item_code:
            continue
        remaining = flt(item_row.get("qty", 0))
        if remaining <= 0:
            continue
        original = remaining

        for dn_name in sorted_dns:
            slot = dn_info[dn_name]["items"].get(item_code)
            if not slot or slot["returnable_qty"] <= 0:
                continue
            allocate = min(remaining, slot["returnable_qty"])
            slot["returnable_qty"] -= allocate
            allocations.setdefault(dn_name, {})[item_code] = (
                allocations.get(dn_name, {}).get(item_code, 0) + allocate
            )
            remaining -= allocate
            if remaining <= 0:
                break

        if remaining > 0:
            fulfilled = flt(original - remaining, 2)
            frappe.throw(
                _("Only {0} of <b>{1}</b> is returnable (requested {2})").format(
                    fulfilled, item_code, flt(original, 2)
                )
            )

    result = []
    for dn_name in sorted_dns:
        if dn_name not in allocations:
            continue
        group_items = []
        for item_code, qty in allocations[dn_name].items():
            slot = dn_info[dn_name]["items"].get(item_code, {})
            group_items.append({
                "item_code": item_code,
                "qty": flt(qty, 3),
                "rate": slot.get("rate", 0),
                "uom": slot.get("uom", "Nos"),
            })
        result.append({
            "dn": dn_name,
            "posting_date": dn_info[dn_name]["posting_date"],
            "items": group_items,
        })
    return result


@frappe.whitelist()
def validate_return_against_dn(source_dn, customer, items):
    """Validate items against a user-chosen DN (called when Step 2 DN picker changes).
    Returns {valid, errors, items, posting_date}.
    """
    if isinstance(items, str):
        items = json.loads(items)

    dn_doc = frappe.get_cached_doc("Delivery Note", source_dn)
    if dn_doc.customer != customer:
        return {"valid": False, "errors": [_("{0} belongs to a different customer").format(source_dn)]}
    if dn_doc.docstatus != 1:
        return {"valid": False, "errors": [_("{0} is not submitted").format(source_dn)]}
    if dn_doc.is_return:
        return {"valid": False, "errors": [_("{0} is itself a return DN").format(source_dn)]}

    item_codes = [r["item_code"] for r in items]

    dn_item_map = {}
    for row in dn_doc.items:
        if row.item_code in item_codes:
            if row.item_code not in dn_item_map:
                dn_item_map[row.item_code] = {"qty": 0, "rate": row.rate, "uom": row.uom}
            dn_item_map[row.item_code]["qty"] += row.qty

    ret_rows = frappe.db.sql("""
        SELECT reti.item_code, SUM(ABS(reti.qty)) AS returned_qty
        FROM `tabDelivery Note` ret
        JOIN `tabDelivery Note Item` reti ON reti.parent = ret.name
        WHERE ret.return_against = %(dn)s
          AND ret.docstatus IN (0, 1)
          AND reti.item_code IN %(codes)s
        GROUP BY reti.item_code
    """, {"dn": source_dn, "codes": item_codes}, as_dict=True)
    returned_map = {r.item_code: flt(r.returned_qty) for r in ret_rows}

    errors = []
    updated_items = []

    for item_row in items:
        item_code = item_row["item_code"]
        requested = flt(item_row["qty"])

        if item_code not in dn_item_map:
            errors.append(_("<b>{0}</b> not found in {1}").format(item_code, source_dn))
            updated_items.append(item_row)
            continue

        returnable = dn_item_map[item_code]["qty"] - returned_map.get(item_code, 0)
        if returnable <= 0:
            errors.append(_("<b>{0}</b> has no returnable qty in {1}").format(item_code, source_dn))
        elif requested > returnable + 0.001:
            errors.append(
                _("Only {0} of <b>{1}</b> returnable from {2}").format(
                    flt(returnable, 2), item_code, source_dn
                )
            )

        updated_items.append({
            "item_code": item_code,
            "qty": min(requested, max(returnable, 0)),
            "rate": dn_item_map[item_code]["rate"],
            "uom": dn_item_map[item_code]["uom"],
        })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "items": updated_items,
        "posting_date": str(dn_doc.posting_date),
    }


@frappe.whitelist()
def create_return_dns_from_allocation(customer, company, allocations):
    """Create one draft Return Delivery Note per allocation group using
    ERPNext's standard make_return_doc mapper.

    allocations: [{dn, items:[{item_code, qty, rate, uom}]}]
    Returns: [created_dn_names]
    """
    from erpnext.controllers.sales_and_purchase_return import make_return_doc

    if isinstance(allocations, str):
        allocations = json.loads(allocations)

    created = []

    for group in allocations:
        source_dn = group["dn"]
        items_map = {r["item_code"]: flt(r["qty"]) for r in group["items"]}

        # ERPNext creates a properly mapped return DN with all fields set
        return_dn = make_return_doc("Delivery Note", source_dn)

        # Keep only the allocated items (remove items not being returned)
        return_dn.items = [row for row in return_dn.items if row.item_code in items_map]

        # Adjust to allocated quantities (make_return_doc already negates)
        for row in return_dn.items:
            alloc_qty = items_map[row.item_code]
            row.qty = -abs(alloc_qty)
            row.stock_qty = row.qty * (flt(row.conversion_factor) or 1)

        return_dn.insert(ignore_permissions=True)
        created.append(return_dn.name)

    return created
