import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	validate_filters(filters)

	columns = [
		{"label": "Item ID", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 240},
		{"label": "Available Quantity", "fieldname": "actual_qty", "fieldtype": "Float", "width": 150},
		{"label": "UOM", "fieldname": "stock_uom", "fieldtype": "Data", "width": 100},
	]

	conditions = []
	if filters.get("company"):
		conditions.append("AND sle.company = %(company)s")
	if filters.get("item_code"):
		conditions.append("AND sle.item_code = %(item_code)s")

	condition_str = " ".join(conditions)

	query = f"""
		SELECT
			sle.item_code,
			i.item_name,
			sle.qty_after_transaction AS actual_qty,
			i.stock_uom
		FROM `tabStock Ledger Entry` sle
		INNER JOIN `tabItem` i ON i.name = sle.item_code
		INNER JOIN (
			SELECT item_code,
				   MAX(CONCAT(posting_date, ' ', posting_time, ' ', LPAD(creation, 30, '0'))) AS max_key
			FROM `tabStock Ledger Entry`
			WHERE warehouse = %(warehouse)s
			  AND company = %(company)s
			  AND (is_cancelled = 0 OR is_cancelled IS NULL)
			  AND posting_date <= %(as_on_date)s
			GROUP BY item_code
		) last_entry ON last_entry.item_code = sle.item_code
			AND CONCAT(sle.posting_date, ' ', sle.posting_time, ' ', LPAD(sle.creation, 30, '0')) = last_entry.max_key
		WHERE sle.warehouse = %(warehouse)s
		  AND (sle.is_cancelled = 0 OR sle.is_cancelled IS NULL)
		  {condition_str}
		HAVING actual_qty != 0
		ORDER BY i.item_name
	"""

	result = frappe.db.sql(query, filters, as_dict=1)
	return columns, result


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is required"))
	if not filters.get("warehouse"):
		frappe.throw(_("Warehouse is required"))
	if not filters.get("as_on_date"):
		frappe.throw(_("As on Date is required"))
