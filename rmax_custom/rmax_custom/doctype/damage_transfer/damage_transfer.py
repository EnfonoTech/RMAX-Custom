# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DamageTransfer(Document):

	def validate(self):
		self._validate_items()
		self._validate_no_duplicate_slips()
		if self.workflow_state == "Approved":
			self._validate_inspection_complete()

	def _validate_items(self):
		"""Ensure items exist and have valid qty."""
		if not self.items:
			frappe.throw(_("Please add at least one item."))
		for item in self.items:
			if not item.item_code:
				frappe.throw(_("Row {0}: Item Code is required.").format(item.idx))
			if flt(item.qty) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than 0.").format(item.idx))

	def _validate_no_duplicate_slips(self):
		"""Ensure a Damage Slip isn't linked to multiple Damage Transfers."""
		for row in self.damage_slips:
			existing = frappe.db.get_value(
				"Damage Slip", row.damage_slip,
				["damage_transfer", "status"], as_dict=True
			)
			if existing and existing.damage_transfer and existing.damage_transfer != self.name:
				frappe.throw(
					_("Damage Slip {0} is already linked to Damage Transfer {1}.").format(
						row.damage_slip, existing.damage_transfer
					)
				)

	def _validate_inspection_complete(self):
		"""Before approval, ensure every item has:
		1. damage_category set
		2. supplier_code set
		3. At least one image uploaded
		"""
		incomplete = []
		for item in self.items:
			missing = []
			if not item.damage_category:
				missing.append("Damage Category")
			if not item.supplier_code:
				missing.append("Supplier Code")
			if not item.images:
				missing.append("Image (at least 1)")
			if missing:
				incomplete.append({
					"idx": item.idx,
					"item_code": item.item_code,
					"missing": ", ".join(missing),
				})

		if incomplete:
			msg = _("Inspection incomplete. The following items are missing required fields:")
			msg += "<br><br><table class='table table-bordered table-sm'>"
			msg += "<thead><tr><th>#</th><th>Item</th><th>Missing</th></tr></thead><tbody>"
			for row in incomplete:
				msg += "<tr><td>{}</td><td>{}</td><td style='color:red'>{}</td></tr>".format(
					row["idx"], row["item_code"], row["missing"]
				)
			msg += "</tbody></table>"
			frappe.throw(msg, title=_("Inspection Incomplete"))

	def on_submit(self):
		"""On approval (submit), create Stock Entry: Material Transfer from branch WH to damage WH."""
		if self.workflow_state != "Approved":
			return
		self._create_transfer_stock_entry()
		self._mark_slips_transferred()

	def _create_transfer_stock_entry(self):
		"""Create Stock Entry (Material Transfer): Branch WH -> Damage WH."""
		damage_wh = frappe.db.get_value("Company", self.company, "custom_damage_warehouse")
		if not damage_wh:
			frappe.throw(
				_("Damage Warehouse is not configured for company {0}. "
				  "Go to Company > Damage Warehouse and set it.").format(self.company)
			)

		self.damage_warehouse = damage_wh

		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Transfer"
		se.from_warehouse = self.branch_warehouse
		se.to_warehouse = damage_wh
		se.company = self.company
		se.remarks = f"Damage Transfer: {self.name} (Branch -> Damage WH)"

		for item in self.items:
			se.append("items", {
				"item_code": item.item_code,
				"qty": item.qty,
				"uom": item.stock_uom,
				"s_warehouse": self.branch_warehouse,
				"t_warehouse": damage_wh,
			})

		se.insert(ignore_permissions=True)
		se.submit()

		self.stock_entry_transfer = se.name
		self.transfer_entry_created = 1
		# Save fields via db_set to avoid re-triggering validate
		self.db_set("stock_entry_transfer", se.name, update_modified=False)
		self.db_set("transfer_entry_created", 1, update_modified=False)
		self.db_set("damage_warehouse", damage_wh, update_modified=False)

		frappe.msgprint(
			_('Stock Entry Created: <a href="/app/stock-entry/{0}">{0}</a>').format(se.name),
			alert=True, indicator="green"
		)

	def _mark_slips_transferred(self):
		"""Mark all linked Damage Slips as Transferred."""
		for row in self.damage_slips:
			frappe.db.set_value("Damage Slip", row.damage_slip, {
				"status": "Transferred",
				"damage_transfer": self.name,
			}, update_modified=False)

	def on_cancel(self):
		"""Revert Damage Slip statuses when cancelled."""
		for row in self.damage_slips:
			frappe.db.set_value("Damage Slip", row.damage_slip, {
				"status": "Open",
				"damage_transfer": "",
			}, update_modified=False)


@frappe.whitelist()
def get_pending_damage_slips(branch_warehouse, company):
	"""Get Damage Slips with status=Open for the given branch warehouse.
	Called by the 'Get Damage Slips' button."""
	slips = frappe.get_all(
		"Damage Slip",
		filters={
			"branch_warehouse": branch_warehouse,
			"company": company,
			"status": "Open",
		},
		fields=["name", "date", "damage_category", "customer", "remarks"],
		order_by="date desc",
	)

	# Enrich with item details
	for slip in slips:
		slip["items"] = frappe.get_all(
			"Damage Slip Item",
			filters={"parent": slip["name"]},
			fields=["item_code", "item_name", "qty", "stock_uom"],
		)
		slip["total_items"] = len(slip["items"])
		slip["total_qty"] = sum(i["qty"] for i in slip["items"])

	return slips


@frappe.whitelist()
def write_off_damage(damage_transfer_name):
	"""Create Stock Entry (Material Issue) to write off damaged items.
	Called by the 'Write Off' button after approval."""
	dt = frappe.get_doc("Damage Transfer", damage_transfer_name)

	if dt.docstatus != 1:
		frappe.throw(_("Damage Transfer must be submitted (Approved) before write-off."))
	if dt.workflow_state != "Approved":
		frappe.throw(_("Damage Transfer must be in Approved state for write-off."))
	if dt.writeoff_entry_created:
		frappe.throw(_("Write-off Stock Entry has already been created."))

	damage_wh = dt.damage_warehouse
	if not damage_wh:
		damage_wh = frappe.db.get_value("Company", dt.company, "custom_damage_warehouse")
	if not damage_wh:
		frappe.throw(_("Damage Warehouse not configured for company {0}.").format(dt.company))

	expense_account = frappe.db.get_value("Company", dt.company, "custom_damage_loss_account")
	if not expense_account:
		frappe.throw(
			_("Damage/Loss Account is not configured for company {0}. "
			  "Go to Company > Damage/Loss Account and set it.").format(dt.company)
		)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Issue"
	se.from_warehouse = damage_wh
	se.company = dt.company
	se.remarks = f"Damage Write-Off: {dt.name}"

	for item in dt.items:
		se.append("items", {
			"item_code": item.item_code,
			"qty": item.qty,
			"uom": item.stock_uom,
			"s_warehouse": damage_wh,
			"expense_account": expense_account,
		})

	se.insert(ignore_permissions=True)
	se.submit()

	# Update Damage Transfer
	dt.db_set("stock_entry_writeoff", se.name, update_modified=False)
	dt.db_set("writeoff_entry_created", 1, update_modified=False)
	dt.db_set("workflow_state", "Written Off", update_modified=False)

	frappe.msgprint(
		_('Write-Off Stock Entry Created: <a href="/app/stock-entry/{0}">{0}</a>').format(se.name),
		alert=True, indicator="green"
	)

	return se.name
