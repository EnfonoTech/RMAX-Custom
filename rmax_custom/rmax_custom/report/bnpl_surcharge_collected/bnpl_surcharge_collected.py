"""BNPL Surcharge Collected — finance reconciliation report.

Aggregates `custom_bnpl_uplift_amount` across submitted Sales Invoices,
broken down by month, BNPL Mode of Payment, and Customer. Lets the
finance team reconcile uplift collected against BNPL provider fees
deducted on settlement.

Per BRD §5.5.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = _get_columns()
    data = _get_data(filters)
    return columns, data


def _get_columns():
    return [
        {
            "fieldname": "month",
            "label": _("Month"),
            "fieldtype": "Data",
            "width": 100,
        },
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
            "width": 180,
        },
        {
            "fieldname": "customer_name",
            "label": _("Customer Name"),
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "mode_of_payment",
            "label": _("BNPL Mode of Payment"),
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "width": 160,
        },
        {
            "fieldname": "bnpl_amount",
            "label": _("BNPL Amount"),
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "fieldname": "uplift_amount",
            "label": _("Uplift Collected"),
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "fieldname": "grand_total",
            "label": _("Invoice Grand Total"),
            "fieldtype": "Currency",
            "width": 150,
        },
    ]


def _get_data(filters):
    conditions = ["si.docstatus = 1", "si.custom_bnpl_portion_ratio > 0"]
    values = {}

    if filters.get("from_date"):
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = filters.from_date
    if filters.get("to_date"):
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = filters.to_date
    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
        values["customer"] = filters.customer
    if filters.get("company"):
        conditions.append("si.company = %(company)s")
        values["company"] = filters.company
    if filters.get("mode_of_payment"):
        conditions.append("p.mode_of_payment = %(mode_of_payment)s")
        values["mode_of_payment"] = filters.mode_of_payment

    where_clause = " AND ".join(conditions)

    invoices = frappe.db.sql(
        f"""
        SELECT
            si.name AS sales_invoice,
            si.posting_date,
            si.customer,
            si.customer_name,
            si.grand_total,
            DATE_FORMAT(si.posting_date, '%%Y-%%m') AS month,
            COALESCE(SUM(sii.custom_bnpl_uplift_amount), 0) AS uplift_amount
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        {("LEFT JOIN `tabSales Invoice Payment` p ON p.parent = si.name" if filters.get("mode_of_payment") else "")}
        WHERE {where_clause}
        GROUP BY si.name
        ORDER BY si.posting_date DESC, si.name
        """,
        values,
        as_dict=True,
    )

    if not invoices:
        return []

    invoice_names = [r.sales_invoice for r in invoices]
    payment_rows = frappe.db.sql(
        """
        SELECT
            p.parent AS sales_invoice,
            p.mode_of_payment,
            p.amount,
            COALESCE(mop.custom_surcharge_percentage, 0) AS surcharge_pct
        FROM `tabSales Invoice Payment` p
        LEFT JOIN `tabMode of Payment` mop ON mop.name = p.mode_of_payment
        WHERE p.parent IN %(names)s
        """,
        {"names": invoice_names},
        as_dict=True,
    )

    payments_by_invoice = {}
    for row in payment_rows:
        payments_by_invoice.setdefault(row.sales_invoice, []).append(row)

    output = []
    for inv in invoices:
        invoice_payments = payments_by_invoice.get(inv.sales_invoice, [])
        bnpl_payments = [p for p in invoice_payments if flt(p.surcharge_pct) > 0]
        bnpl_total = sum(flt(p.amount) for p in bnpl_payments) or 1.0

        if not bnpl_payments:
            continue

        for p in bnpl_payments:
            share = flt(p.amount) / bnpl_total if bnpl_total else 0.0
            output.append(
                {
                    "month": inv.month,
                    "posting_date": inv.posting_date,
                    "sales_invoice": inv.sales_invoice,
                    "customer": inv.customer,
                    "customer_name": inv.customer_name,
                    "mode_of_payment": p.mode_of_payment,
                    "bnpl_amount": flt(p.amount),
                    "uplift_amount": flt(inv.uplift_amount * share, 2),
                    "grand_total": flt(inv.grand_total),
                }
            )

    return output
