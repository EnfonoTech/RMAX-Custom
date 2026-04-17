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
		# Stock availability fires on every save while still a draft so branch
		# users see shortages immediately — before wasting the inspector's time.
		# Skip once submitted (docstatus==1) to avoid blocking cancel/amend flows.
		if self.docstatus == 0:
			self._validate_stock_availability()
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

	def _validate_stock_availability(self):
		"""Before approval, ensure the branch warehouse has enough stock for every
		item. Catches the shortage here with a clear tabular message rather than
		letting the Stock Entry submit later raise ERPNext's HTML-laden negative
		stock error.
		"""
		if not self.branch_warehouse:
			frappe.throw(_("Please select a Branch Warehouse before approving."))

		# Aggregate required qty per item (same item can span multiple rows)
		required = {}
		for item in self.items:
			required[item.item_code] = required.get(item.item_code, 0) + flt(item.qty)

		if not required:
			return

		# Fetch actual_qty from Bin in one query
		item_codes = list(required.keys())
		bins = frappe.get_all(
			"Bin",
			filters={"warehouse": self.branch_warehouse, "item_code": ["in", item_codes]},
			fields=["item_code", "actual_qty"],
		)
		available = {b.item_code: flt(b.actual_qty) for b in bins}

		shortages = []
		for code, needed in required.items():
			have = available.get(code, 0.0)
			if have < needed:
				shortages.append({
					"item_code": code,
					"available": have,
					"needed": needed,
					"short": needed - have,
				})

		if not shortages:
			return

		item_names = {
			r["name"]: r["item_name"]
			for r in frappe.get_all(
				"Item",
				filters={"name": ["in", [s["item_code"] for s in shortages]]},
				fields=["name", "item_name"],
			)
		}

		msg = _("Cannot approve. Insufficient stock in {0} for the following items:").format(
			frappe.bold(self.branch_warehouse)
		)
		msg += "<br><br><table class='table table-bordered table-sm'>"
		msg += ("<thead><tr><th>Item</th><th>Item Name</th>"
		        "<th style='text-align:right'>Available</th>"
		        "<th style='text-align:right'>Needed</th>"
		        "<th style='text-align:right;color:red'>Short</th></tr></thead><tbody>")
		for s in shortages:
			msg += (
				"<tr>"
				"<td>{code}</td>"
				"<td>{name}</td>"
				"<td style='text-align:right'>{have}</td>"
				"<td style='text-align:right'>{need}</td>"
				"<td style='text-align:right;color:red'><b>{short}</b></td>"
				"</tr>"
			).format(
				code=s["item_code"],
				name=item_names.get(s["item_code"], ""),
				have=s["available"],
				need=s["needed"],
				short=s["short"],
			)
		msg += "</tbody></table>"
		msg += "<br>" + _(
			"Add opening stock or reconcile inventory for the above items in {0}, "
			"then approve again."
		).format(frappe.bold(self.branch_warehouse))
		frappe.throw(msg, title=_("Insufficient Stock"))

	def on_submit(self):
		"""On approval (submit), create Stock Entry: Material Transfer from branch WH to damage WH."""
		if self.workflow_state != "Approved":
			return
		self._create_transfer_stock_entry()
		self._mark_slips_transferred()

	def _create_transfer_stock_entry(self):
		"""Create Stock Entry (Material Transfer): Branch WH -> Damage WH.
		Uses the user-selected damage_warehouse (not Company default).
		No GL entry is created — only Stock Ledger moves qty between warehouses.
		"""
		if not self.damage_warehouse:
			frappe.throw(
				_("Please select a Damage Warehouse before approving.")
			)

		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Transfer"
		se.from_warehouse = self.branch_warehouse
		se.to_warehouse = self.damage_warehouse
		se.company = self.company
		se.remarks = f"Damage Transfer: {self.name} ({self.branch_warehouse} → {self.damage_warehouse})"

		for item in self.items:
			se.append("items", {
				"item_code": item.item_code,
				"qty": item.qty,
				"uom": item.stock_uom,
				"s_warehouse": self.branch_warehouse,
				"t_warehouse": self.damage_warehouse,
			})

		se.insert(ignore_permissions=True)
		se.submit()

		self.stock_entry_transfer = se.name
		self.transfer_entry_created = 1
		# Save fields via db_set to avoid re-triggering validate
		self.db_set("stock_entry_transfer", se.name, update_modified=False)
		self.db_set("transfer_entry_created", 1, update_modified=False)

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
		fields=["name", "date", "damage_category", "customer", "remarks", "damage_warehouse"],
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
		frappe.throw(_("Damage Warehouse is not set on this Damage Transfer."))

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
