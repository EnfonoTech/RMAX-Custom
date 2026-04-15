# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class WarehousePickList(Document):

	def before_save(self):
		if self.docstatus == 0 and self.items:
			self.status = "Picking"

	def before_submit(self):
		self.status = "Completed"

	def before_cancel(self):
		self.status = "Cancelled"


@frappe.whitelist()
def get_pending_material_requests(warehouse):
	"""List pending Material Requests for the given source warehouse.
	Excludes MRs already added to any non-cancelled Warehouse Pick List.
	"""
	if not warehouse:
		frappe.throw(_("Please select a Source Warehouse first"))

	# Get MRs already picked in any active (non-cancelled) pick list
	already_picked = _get_already_picked_docs("Material Request")

	mrs = frappe.db.sql(
		"""
		SELECT DISTINCT
			mr.name, mr.transaction_date, mr.set_warehouse,
			mr.set_from_warehouse, mr.status,
			(SELECT GROUP_CONCAT(mri2.item_name SEPARATOR ', ')
			 FROM `tabMaterial Request Item` mri2 WHERE mri2.parent = mr.name LIMIT 3
			) AS item_summary,
			(SELECT COUNT(*) FROM `tabMaterial Request Item` mri3 WHERE mri3.parent = mr.name
			) AS item_count,
			(SELECT MAX(mri4.custom_is_urgent) FROM `tabMaterial Request Item` mri4 WHERE mri4.parent = mr.name
			) AS has_urgent
		FROM `tabMaterial Request` mr
		INNER JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE mr.docstatus = 1
		AND mr.status IN ('Pending', 'Partially Ordered')
		AND mr.material_request_type = 'Material Transfer'
		AND (mr.set_from_warehouse = %s OR mri.from_warehouse = %s)
		ORDER BY has_urgent DESC, mr.name DESC
		""",
		(warehouse, warehouse),
		as_dict=True,
	)

	# Filter out already picked
	if already_picked:
		mrs = [mr for mr in mrs if mr.name not in already_picked]

	return mrs


@frappe.whitelist()
def get_pending_stock_transfers(warehouse):
	"""List pending Stock Transfers for the given source warehouse.
	Excludes STs already added to any non-cancelled Warehouse Pick List.
	"""
	if not warehouse:
		frappe.throw(_("Please select a Source Warehouse first"))

	# Get STs already picked in any active pick list
	already_picked = _get_already_picked_docs("Stock Transfer")

	sts = frappe.db.sql(
		"""
		SELECT DISTINCT
			st.name, st.transaction_date, st.set_source_warehouse,
			st.set_target_warehouse, st.workflow_state,
			(SELECT GROUP_CONCAT(sti2.item_name SEPARATOR ', ')
			 FROM `tabStock Transfer Item` sti2 WHERE sti2.parent = st.name LIMIT 3
			) AS item_summary,
			(SELECT COUNT(*) FROM `tabStock Transfer Item` sti3 WHERE sti3.parent = st.name
			) AS item_count
		FROM `tabStock Transfer` st
		INNER JOIN `tabStock Transfer Item` sti ON sti.parent = st.name
		WHERE st.docstatus = 0
		AND st.workflow_state = 'Waiting for Approval'
		AND st.set_source_warehouse = %s
		ORDER BY st.name DESC
		""",
		(warehouse,),
		as_dict=True,
	)

	# Filter out already picked
	if already_picked:
		sts = [st for st in sts if st.name not in already_picked]

	return sts


def _get_already_picked_docs(source_doctype):
	"""Get set of document names already added to any non-cancelled Warehouse Pick List."""
	picked = frappe.db.sql(
		"""
		SELECT DISTINCT wps.source_name
		FROM `tabWarehouse Pick List Source` wps
		INNER JOIN `tabWarehouse Pick List` wpl ON wpl.name = wps.parent
		WHERE wps.source_doctype = %s
		AND wpl.docstatus != 2
		""",
		(source_doctype,),
		as_list=True,
	)
	return set(row[0] for row in picked)


@frappe.whitelist()
def get_items_from_document(source_doctype, source_name, warehouse):
	"""Fetch items from a specific MR or ST document.

	Returns:
		dict with 'items' list and 'sources' list
	"""
	if not warehouse:
		frappe.throw(_("Please select a Source Warehouse first"))

	items = []
	sources = []

	if source_doctype == "Material Request":
		rows = frappe.db.sql(
			"""
			SELECT mri.item_code, mri.item_name, mri.qty, mri.stock_uom,
				mri.custom_is_urgent
			FROM `tabMaterial Request Item` mri
			WHERE mri.parent = %s
			""",
			(source_name,),
			as_dict=True,
		)
		for row in rows:
			qty = flt(row.qty)
			is_urgent = 1 if row.custom_is_urgent else 0
			available = flt(
				frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": warehouse}, "actual_qty")
			)
			items.append({
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty_to_pick": qty,
				"available_qty": available,
				"uom": row.stock_uom,
				"is_urgent": is_urgent,
				"source_documents": f"{source_name} ({qty})",
			})
			sources.append({
				"source_doctype": "Material Request",
				"source_name": source_name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": qty,
				"is_urgent": is_urgent,
			})

	elif source_doctype == "Stock Transfer":
		rows = frappe.db.sql(
			"""
			SELECT sti.item_code, sti.item_name, sti.quantity AS qty, sti.stock_uom
			FROM `tabStock Transfer Item` sti
			WHERE sti.parent = %s
			""",
			(source_name,),
			as_dict=True,
		)
		for row in rows:
			qty = flt(row.qty)
			available = flt(
				frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": warehouse}, "actual_qty")
			)
			items.append({
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty_to_pick": qty,
				"available_qty": available,
				"uom": row.stock_uom,
				"is_urgent": 0,
				"source_documents": f"{source_name} ({qty})",
			})
			sources.append({
				"source_doctype": "Stock Transfer",
				"source_name": source_name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": qty,
				"is_urgent": 0,
			})
	else:
		frappe.throw(_("Invalid source document type"))

	return {"items": items, "sources": sources}


