# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.data import get_url_to_form


class StockTransfer(Document):
	


	def on_submit(self):
		"""Run only when document is submitted (docstatus = 1)"""
		if self.workflow_state != "Approved":
			return

		self.create_stock_entry()


	def create_stock_entry(self):
		"""Create Stock Entry for Material Transfer"""
		if not self.set_target_warehouse:
			frappe.throw("Target Warehouse is required")
		if not self.set_source_warehouse:
			frappe.throw("Source Warehouse is required")
		if not self.items:
			frappe.throw("No items found")
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Transfer"
		se.from_warehouse = self.set_source_warehouse
		se.company = self.company
		se.to_warehouse = self.set_target_warehouse
		se.remarks = f"Created from Stock Transfer: {self.name}"
		for item in self.items:
			if item.item_code:
				se.append("items", {
					"item_code": item.item_code,
					"qty": item.quantity,
					"uom": item.uom,
					"s_warehouse": self.set_source_warehouse,
					"t_warehouse": self.set_target_warehouse
				})
		se.insert()
		self.stock_entry = se.name
		self.stock_entry_created = 1
		se.submit()
		frappe.msgprint(
			f'Stock Entry Created: <a href="/app/stock-entry/{se.name}">{se.name}</a>',
			alert=True,
			indicator='green'
		)

		

@frappe.whitelist()
def get_item_uom_conversion(item_code, uom):
    data = frappe.db.get_value(
        "UOM Conversion Detail",
        {"parent": item_code, "uom": uom},
        "conversion_factor"
    )
    return data or 1