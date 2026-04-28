"""
BNPL Surcharge Collected report.

Source: tabSales Invoice rows where custom_bnpl_total_uplift > 0. The total
uplift on each invoice is attributed to BNPL Modes of Payment by parsing
custom_pos_payments_json (the snapshot stamped by the POS payment popup
before frm.save()). The attribution is proportional to each BNPL row's
amount within the invoice's BNPL total.

Filters: Company (required), From Date, To Date, Mode of Payment (optional).
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = _columns()
    rows = _rows(filters)
    return columns, rows


def _columns():
    return [
        {
            "label": "Sales Invoice",
            "fieldname": "sales_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 160,
        },
        {
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 180,
        },
        {
            "label": "Mode of Payment",
            "fieldname": "mode_of_payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "width": 140,
        },
        {
            "label": "BNPL Uplift Attributed",
            "fieldname": "uplift",
            "fieldtype": "Currency",
            "width": 160,
        },
        {
            "label": "Original Items Total",
            "fieldname": "original_total",
            "fieldtype": "Currency",
            "width": 160,
        },
    ]


def _rows(filters):
    conds = ["si.docstatus = 1", "IFNULL(si.custom_bnpl_total_uplift, 0) > 0"]
    args = {}
    if filters.get("company"):
        conds.append("si.company = %(company)s")
        args["company"] = filters["company"]
    if filters.get("from_date"):
        conds.append("si.posting_date >= %(from_date)s")
        args["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conds.append("si.posting_date <= %(to_date)s")
        args["to_date"] = filters["to_date"]

    sql = f"""
        SELECT
            si.name AS sales_invoice,
            si.posting_date,
            si.customer,
            si.custom_bnpl_total_uplift,
            si.custom_pos_payments_json,
            (
                SELECT COALESCE(SUM(sii.qty * sii.custom_original_rate), 0)
                FROM `tabSales Invoice Item` sii
                WHERE sii.parent = si.name
            ) AS original_total
        FROM `tabSales Invoice` si
        WHERE {' AND '.join(conds)}
        ORDER BY si.posting_date DESC, si.name DESC
    """
    raw = frappe.db.sql(sql, args, as_dict=True)

    out = []
    mop_filter = filters.get("mode_of_payment")
    for r in raw:
        attrib = _attribute_uplift(r)
        for mop, share in attrib.items():
            if mop_filter and mop != mop_filter:
                continue
            out.append(
                {
                    "sales_invoice": r.sales_invoice,
                    "posting_date": r.posting_date,
                    "customer": r.customer,
                    "mode_of_payment": mop,
                    "uplift": flt(share),
                    "original_total": flt(r.original_total),
                }
            )
    return out


def _attribute_uplift(row):
    """Distribute custom_bnpl_total_uplift across BNPL Modes of Payment.

    Reads the JSON snapshot stamped by the POS popup. For each row in the
    snapshot whose Mode of Payment carries a positive
    custom_surcharge_percentage, accumulate the amount; the share is
    `total_uplift * (mop_amount / sum_of_all_bnpl_amounts)`.

    Returns a `{mode_of_payment: attributed_uplift}` dict. Empty dict if
    the snapshot is missing or has no BNPL rows.
    """
    raw = row.get("custom_pos_payments_json")
    total_uplift = flt(row.get("custom_bnpl_total_uplift"))
    if not raw or total_uplift <= 0:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = []
    if not isinstance(parsed, list):
        return {}

    bnpl_modes: dict[str, float] = {}
    bnpl_total = 0.0
    for p in parsed:
        if not isinstance(p, dict):
            continue
        mop = p.get("mode_of_payment")
        amt = flt(p.get("amount"))
        if not mop or amt <= 0:
            continue
        pct = flt(
            frappe.db.get_value(
                "Mode of Payment", mop, "custom_surcharge_percentage"
            )
        )
        if pct > 0:
            bnpl_modes[mop] = bnpl_modes.get(mop, 0.0) + amt
            bnpl_total += amt

    if bnpl_total <= 0:
        return {}
    return {mop: total_uplift * (amt / bnpl_total) for mop, amt in bnpl_modes.items()}
