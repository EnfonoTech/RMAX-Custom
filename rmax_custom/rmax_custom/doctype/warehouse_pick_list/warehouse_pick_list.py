# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class WarehousePickList(Document):

	def before_submit(self):
		self.status = "Open"

	def before_cancel(self):
		self.status = "Cancelled"


@frappe.whitelist()
def get_pending_items(warehouse):
	"""Fetch pending items from Material Requests and Stock Transfers
	for the given source warehouse. Consolidates same items and sums qty.

	Returns:
		dict with 'items' (consolidated) and 'sources' (individual line items)
	"""
	if not warehouse:
		frappe.throw(_("Please select a Source Warehouse first"))

	sources = []
	item_map = {}  # item_code -> {qty, uom, is_urgent, refs[]}

	# 1. Pending Material Requests (Material Transfer type)
	#    where set_from_warehouse = this warehouse (source)
	mr_items = frappe.db.sql(
		"""
		SELECT
			mri.item_code, mri.item_name, mri.qty, mri.stock_uom,
			mri.custom_is_urgent, mri.parent AS mr_name
		FROM `tabMaterial Request Item` mri
		INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
		WHERE mr.docstatus = 1
		AND mr.status IN ('Pending', 'Partially Ordered')
		AND mr.material_request_type = 'Material Transfer'
		AND (mr.set_from_warehouse = %s OR mri.from_warehouse = %s)
		ORDER BY mri.custom_is_urgent DESC, mr.transaction_date ASC
		""",
		(warehouse, warehouse),
		as_dict=True,
	)

	for row in mr_items:
		item_code = row.item_code
		qty = flt(row.qty)
		is_urgent = 1 if row.custom_is_urgent else 0

		sources.append({
			"source_doctype": "Material Request",
			"source_name": row.mr_name,
			"item_code": item_code,
			"item_name": row.item_name,
			"qty": qty,
			"is_urgent": is_urgent,
		})

		if item_code not in item_map:
			item_map[item_code] = {
				"item_name": row.item_name,
				"qty": 0,
				"uom": row.stock_uom,
				"is_urgent": 0,
				"refs": [],
			}
		item_map[item_code]["qty"] += qty
		if is_urgent:
			item_map[item_code]["is_urgent"] = 1
		item_map[item_code]["refs"].append(f"{row.mr_name} ({qty})")

	# 2. Pending Stock Transfers (Waiting for Approval)
	#    where set_source_warehouse = this warehouse
	st_items = frappe.db.sql(
		"""
		SELECT
			sti.item_code, sti.item_name, sti.quantity AS qty, sti.stock_uom,
			sti.parent AS st_name
		FROM `tabStock Transfer Item` sti
		INNER JOIN `tabStock Transfer` st ON st.name = sti.parent
		WHERE st.docstatus = 0
		AND st.workflow_state = 'Waiting for Approval'
		AND st.set_source_warehouse = %s
		ORDER BY st.transaction_date ASC
		""",
		(warehouse,),
		as_dict=True,
	)

	for row in st_items:
		item_code = row.item_code
		qty = flt(row.qty)

		sources.append({
			"source_doctype": "Stock Transfer",
			"source_name": row.st_name,
			"item_code": item_code,
			"item_name": row.item_name,
			"qty": qty,
			"is_urgent": 0,
		})

		if item_code not in item_map:
			item_map[item_code] = {
				"item_name": row.item_name,
				"qty": 0,
				"uom": row.stock_uom,
				"is_urgent": 0,
				"refs": [],
			}
		item_map[item_code]["qty"] += qty
		item_map[item_code]["refs"].append(f"{row.st_name} ({qty})")

	# 3. Build consolidated items list (urgent first, then alphabetical)
	items = []
	for item_code, data in item_map.items():
		# Get available qty from Bin
		available = flt(
			frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
		)
		items.append({
			"item_code": item_code,
			"item_name": data["item_name"],
			"qty_to_pick": data["qty"],
			"available_qty": available,
			"uom": data["uom"],
			"is_urgent": data["is_urgent"],
			"source_documents": ", ".join(data["refs"]),
		})

	# Sort: urgent first, then by item_code
	items.sort(key=lambda x: (-x["is_urgent"], x["item_code"]))

	if not items:
		frappe.msgprint(
			_("No pending items found for warehouse <b>{0}</b>").format(warehouse),
			indicator="orange",
			alert=True,
		)

	return {"items": items, "sources": sources}


@frappe.whitelist()
def mark_completed(name):
	"""Mark a submitted Warehouse Pick List as Completed."""
	doc = frappe.get_doc("Warehouse Pick List", name)
	if doc.docstatus != 1:
		frappe.throw(_("Only submitted pick lists can be marked as completed"))
	doc.status = "Completed"
	doc.save(ignore_permissions=True)
	return "ok"
