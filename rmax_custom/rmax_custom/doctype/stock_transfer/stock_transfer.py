# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import get_url_to_form


class StockTransfer(Document):

	def validate(self):
		"""Branch-based approval: only target branch users can approve/reject."""
		if self.workflow_state in ("Approved", "Rejected"):
			self._validate_target_branch_user()

	def _validate_target_branch_user(self):
		"""Check that the current user belongs to the target warehouse's branch."""
		if frappe.session.user == "Administrator":
			return

		target_wh = self.set_target_warehouse
		if not target_wh:
			return

		# Find Branch Configuration(s) that contain this target warehouse
		branch_configs = frappe.get_all(
			"Branch Configuration Warehouse",
			filters={"warehouse": target_wh},
			fields=["parent"],
		)

		if not branch_configs:
			frappe.throw(
				_("No Branch Configuration found for target warehouse {0}. "
				  "Please ask an administrator to set one up.").format(target_wh)
			)

		# Get all users from the target branch
		branch_name = branch_configs[0].parent
		branch_users = frappe.get_all(
			"Branch Configuration User",
			filters={"parent": branch_name},
			pluck="user",
		)

		if frappe.session.user not in branch_users:
			frappe.throw(
				_("Only users from the target branch <b>{0}</b> can {1} this Stock Transfer.").format(
					branch_name,
					"approve" if self.workflow_state == "Approved" else "reject",
				)
			)

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
