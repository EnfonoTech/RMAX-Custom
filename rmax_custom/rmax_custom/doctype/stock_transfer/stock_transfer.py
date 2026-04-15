# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.data import get_url_to_form


class StockTransfer(Document):

	def validate(self):
		"""Branch-based approval: only target branch users can approve/reject."""
		if self.workflow_state in ("Approved", "Rejected"):
			self._validate_target_branch_user()

	def before_submit(self):
		"""Validate stock availability before submitting (approval)."""
		if self.workflow_state == "Approved":
			self._validate_stock_availability()

	def _validate_target_branch_user(self):
		"""Check that the current user belongs to the target warehouse's branch.
		Also prevents the creator from approving their own transfer."""
		if frappe.session.user == "Administrator":
			return

		# Prevent self-approval — creator cannot approve their own transfer
		if self.workflow_state == "Approved" and frappe.session.user == self.owner:
			frappe.throw(
				_("You cannot approve a Stock Transfer that you created. "
				  "It must be approved by another user from the target branch.")
			)

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

	def _validate_stock_availability(self):
		"""Check stock availability for all items before creating Stock Entry.
		Throws a clear error listing all insufficient items."""
		if not self.set_source_warehouse or not self.items:
			return

		shortage_items = []
		for item in self.items:
			if not item.item_code:
				continue
			available = get_available_qty(item.item_code, self.set_source_warehouse)
			needed = flt(item.quantity)
			if flt(available) < needed:
				shortage_items.append({
					"item_code": item.item_code,
					"item_name": item.item_name or item.item_code,
					"needed": needed,
					"available": flt(available),
				})

		if shortage_items:
			msg = _("Insufficient stock in <b>{0}</b> for the following items:").format(
				self.set_source_warehouse
			)
			msg += "<br><br><table class='table table-bordered table-sm'>"
			msg += "<thead><tr><th>{}</th><th>{}</th><th>{}</th><th>{}</th></tr></thead>".format(
				_("Item Code"), _("Item Name"), _("Required Qty"), _("Available Qty")
			)
			msg += "<tbody>"
			for s in shortage_items:
				msg += "<tr><td>{}</td><td>{}</td><td>{}</td><td style='color:red;font-weight:bold'>{}</td></tr>".format(
					s["item_code"], s["item_name"], s["needed"], s["available"]
				)
			msg += "</tbody></table>"
			msg += "<br>" + _("Please adjust quantities or ensure stock is available before approving.")
			frappe.throw(msg, title=_("Insufficient Stock"))

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


def get_available_qty(item_code, warehouse):
	"""Get available qty from Bin (actual_qty)."""
	actual_qty = frappe.db.get_value(
		"Bin",
		{"item_code": item_code, "warehouse": warehouse},
		"actual_qty",
	)
	return flt(actual_qty)


@frappe.whitelist()
def get_item_uom_conversion(item_code, uom):
    data = frappe.db.get_value(
        "UOM Conversion Detail",
        {"parent": item_code, "uom": uom},
        "conversion_factor"
    )
    return data or 1


@frappe.whitelist()
def get_items_available_qty(items, warehouse):
	"""Get available qty for multiple items in a warehouse.
	Args:
		items: JSON list of item_codes
		warehouse: source warehouse name
	Returns:
		dict: {item_code: available_qty}
	"""
	import json
	if isinstance(items, str):
		items = json.loads(items)

	result = {}
	for item_code in items:
		result[item_code] = get_available_qty(item_code, warehouse)
	return result
