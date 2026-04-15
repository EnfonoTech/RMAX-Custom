# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DamageSlip(Document):

	def validate(self):
		self._validate_items()
		self._set_branch_warehouse_from_user()

	def _validate_items(self):
		"""Ensure at least one item with qty > 0."""
		if not self.items:
			frappe.throw(_("Please add at least one item."))
		for item in self.items:
			if not item.item_code:
				frappe.throw(_("Row {0}: Item Code is required.").format(item.idx))
			if (item.qty or 0) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than 0.").format(item.idx))

	def _set_branch_warehouse_from_user(self):
		"""Auto-set branch_warehouse from user's default warehouse if not set."""
		if not self.branch_warehouse:
			from rmax_custom.branch_filters import get_branch_warehouse_condition
			warehouses = get_branch_warehouse_condition(frappe.session.user)
			if warehouses and len(warehouses) == 1:
				self.branch_warehouse = warehouses[0]

	def on_trash(self):
		"""Prevent deleting slips that are linked to a Damage Transfer."""
		if self.damage_transfer:
			frappe.throw(
				_("Cannot delete this Damage Slip because it is linked to Damage Transfer {0}.").format(
					self.damage_transfer
				)
			)
