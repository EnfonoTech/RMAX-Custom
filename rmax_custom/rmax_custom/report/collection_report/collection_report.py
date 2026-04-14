# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_months, today
from rmax_custom.branch_filters import get_branch_warehouse_condition


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Invoice",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 180,
        },
        {
            "label": "Customer",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Grand Total",
            "fieldname": "grand_total",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": "Paid Amount",
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": "Outstanding Amount",
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100,
        },
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    warehouse_condition = get_warehouse_condition(filters)

    data = frappe.db.sql(
        """
        SELECT
            si.posting_date,
            si.name,
            si.customer_name,
            si.grand_total,
            (si.grand_total - si.outstanding_amount) AS paid_amount,
            si.outstanding_amount,
            si.status
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
            {conditions}
            {warehouse_condition}
        ORDER BY si.posting_date DESC, si.name DESC
        """.format(
            conditions=conditions,
            warehouse_condition=warehouse_condition,
        ),
        filters,
        as_dict=True,
    )

    return data


def get_conditions(filters):
    conditions = ""

    if filters.get("from_date"):
        conditions += " AND si.posting_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND si.posting_date <= %(to_date)s"

    if filters.get("company"):
        conditions += " AND si.company = %(company)s"

    if filters.get("status"):
        conditions += " AND si.status = %(status)s"

    return conditions


def get_warehouse_condition(filters):
    """Filter invoices by branch user's warehouses via set_warehouse."""
    warehouses = get_branch_warehouse_condition()
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""AND (
        si.set_warehouse IN ({wh_list})
        OR si.name IN (
            SELECT DISTINCT parent FROM `tabSales Invoice Item`
            WHERE warehouse IN ({wh_list})
        )
    )"""
