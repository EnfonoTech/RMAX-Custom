# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

"""Branch Receivables Report.

Shows outstanding Sales Invoices grouped by branch.
Managers can filter by branch; branch-scoped roles see all branches
(report is Accounts/Sales Manager level — no row-level branch filtering).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Branch"),
			"fieldname": "branch",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Invoice"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 180,
		},
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Due Date"),
			"fieldname": "due_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Grand Total"),
			"fieldname": "grand_total",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Paid Amount"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Outstanding"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Age (Days)"),
			"fieldname": "age_days",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100,
		},
	]


def get_data(filters):
	today = getdate(nowdate())
	conditions = _build_conditions(filters)

	rows = frappe.db.sql(
		"""
		SELECT
			si.name,
			si.posting_date,
			si.due_date,
			si.customer,
			si.customer_name,
			si.grand_total,
			(si.grand_total - si.outstanding_amount) AS paid_amount,
			si.outstanding_amount,
			si.status,
			si.set_warehouse
		FROM `tabSales Invoice` si
		WHERE
			si.docstatus = 1
			AND si.outstanding_amount > 0
			{conditions}
		ORDER BY si.posting_date ASC, si.name ASC
		""".format(conditions=conditions),
		filters,
		as_dict=True,
	)

	# Resolve branch from set_warehouse via Branch Configuration Warehouse mapping
	wh_branch_map = _build_warehouse_branch_map()

	result = []
	for row in rows:
		branch = wh_branch_map.get(row.set_warehouse or "", "") or ""

		# Apply branch filter if set
		if filters.get("branch") and branch != filters["branch"]:
			continue

		age_days = (today - getdate(row.posting_date)).days if row.posting_date else 0

		# Apply overdue filter
		if cint(filters.get("overdue_only")):
			if not row.due_date or getdate(row.due_date) >= today:
				continue

		result.append({
			"branch": branch or "—",
			"name": row.name,
			"posting_date": row.posting_date,
			"due_date": row.due_date,
			"customer_name": row.customer_name,
			"grand_total": flt(row.grand_total),
			"paid_amount": flt(row.paid_amount),
			"outstanding_amount": flt(row.outstanding_amount),
			"age_days": age_days,
			"status": row.status,
		})

	# Sort: branch → posting_date
	result.sort(key=lambda r: (r["branch"], r["posting_date"] or ""))
	return result


def _build_conditions(filters):
	conditions = []

	if filters.get("company"):
		conditions.append("AND si.company = %(company)s")

	if filters.get("from_date"):
		conditions.append("AND si.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("AND si.posting_date <= %(to_date)s")

	if filters.get("customer"):
		conditions.append("AND si.customer = %(customer)s")

	return " ".join(conditions)


def _build_warehouse_branch_map():
	"""Return {warehouse: branch_name} from Branch Configuration Warehouse child table."""
	rows = frappe.get_all(
		"Branch Configuration Warehouse",
		fields=["warehouse", "parent"],
		filters={"warehouse": ["!=", ""]},
	)
	return {r.warehouse: r.parent for r in rows}
