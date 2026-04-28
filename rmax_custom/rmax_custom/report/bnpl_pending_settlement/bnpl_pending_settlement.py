"""BNPL Pending Settlement.

Lists submitted BNPL-funded Sales Invoices that have not yet been
matched to a BNPL Settlement document. Lets the finance team see
exactly how much money each provider still owes the merchant.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = _columns()
    data = _data(filters)
    return columns, data


def _columns():
    return [
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "fieldname": "sales_invoice",
            "label": _("Sales Invoice"),
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 180,
        },
        {
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 200,
        },
        {
            "fieldname": "mode_of_payment",
            "label": _("BNPL Mode of Payment"),
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "width": 150,
        },
        {
            "fieldname": "bnpl_amount",
            "label": _("BNPL Receivable (Gross)"),
            "fieldtype": "Currency",
            "width": 160,
        },
        {
            "fieldname": "uplift_amount",
            "label": _("Surcharge Embedded"),
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "fieldname": "expected_net",
            "label": _("Expected Bank Credit"),
            "fieldtype": "Currency",
            "width": 160,
        },
        {
            "fieldname": "expected_fee",
            "label": _("Expected Provider Fee"),
            "fieldtype": "Currency",
            "width": 160,
        },
        {
            "fieldname": "grand_total",
            "label": _("Invoice Grand Total"),
            "fieldtype": "Currency",
            "width": 150,
        },
    ]


def _data(filters):
    conditions = [
        "si.docstatus = 1",
        "COALESCE(si.custom_bnpl_settled, 0) = 0",
        "COALESCE(mop.custom_surcharge_percentage, 0) > 0",
    ]
    values = {}

    if filters.get("from_date"):
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = filters.from_date
    if filters.get("to_date"):
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = filters.to_date
    if filters.get("company"):
        conditions.append("si.company = %(company)s")
        values["company"] = filters.company
    if filters.get("mode_of_payment"):
        conditions.append("p.mode_of_payment = %(mode_of_payment)s")
        values["mode_of_payment"] = filters.mode_of_payment

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            si.posting_date,
            si.name AS sales_invoice,
            si.customer,
            si.grand_total,
            p.mode_of_payment,
            COALESCE(SUM(p.amount), 0) AS bnpl_amount,
            COALESCE(MAX(mop.custom_surcharge_percentage), 0) AS surcharge_pct,
            COALESCE((
                SELECT SUM(sii.custom_bnpl_uplift_amount)
                FROM `tabSales Invoice Item` sii
                WHERE sii.parent = si.name
            ), 0) AS uplift_amount
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Payment` p ON p.parent = si.name
        INNER JOIN `tabMode of Payment` mop ON mop.name = p.mode_of_payment
        WHERE {where_clause}
        GROUP BY si.name, p.mode_of_payment
        ORDER BY si.posting_date, si.name
        """,
        values,
        as_dict=True,
    )

    output = []
    for row in rows:
        bnpl_amount = flt(row.bnpl_amount)
        pct = flt(row.surcharge_pct)
        # Provider's commission = gross * (pct / (100 + pct)) so that
        # net = gross / (1 + pct/100).
        if pct > 0:
            expected_fee = flt(bnpl_amount * (pct / (100 + pct)), 2)
        else:
            expected_fee = 0.0
        expected_net = flt(bnpl_amount - expected_fee, 2)

        output.append(
            {
                "posting_date": row.posting_date,
                "sales_invoice": row.sales_invoice,
                "customer": row.customer,
                "mode_of_payment": row.mode_of_payment,
                "bnpl_amount": bnpl_amount,
                "uplift_amount": flt(row.uplift_amount),
                "expected_fee": expected_fee,
                "expected_net": expected_net,
                "grand_total": flt(row.grand_total),
            }
        )

    return output
