import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DeliveryReturn(Document):

	def validate(self):
		self._set_posting_date_time()
		self._validate_items()
		self._calculate_amounts()

	def _set_posting_date_time(self):
		if not self.set_posting_time:
			now = frappe.utils.now_datetime()
			self.posting_date = now.date()
			self.posting_time = now.strftime("%H:%M:%S")

	def _validate_items(self):
		for row in self.items:
			if not row.against_delivery_note:
				frappe.throw(
					_("Row {0}: Against Delivery Note is required. "
					  "Set the item code first to auto-fetch it.").format(row.idx)
				)
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than 0").format(row.idx))

	def _calculate_amounts(self):
		for row in self.items:
			row.amount = flt(row.qty) * flt(row.rate)

	def on_cancel(self):
		self._cancel_return_delivery_notes()

	def _cancel_return_delivery_notes(self):
		if not self.created_return_dns:
			return
		dns = [n.strip() for n in self.created_return_dns.split(",") if n.strip()]
		cancelled = []
		for dn_name in dns:
			if not frappe.db.exists("Delivery Note", dn_name):
				continue
			dn_doc = frappe.get_doc("Delivery Note", dn_name)
			if dn_doc.docstatus == 1:
				dn_doc.cancel()
				cancelled.append(dn_name)
			elif dn_doc.docstatus == 0:
				dn_doc.delete(ignore_permissions=True)
		if cancelled:
			frappe.msgprint(
				_("Also cancelled: {0}").format(", ".join(
					f'<a href="/app/delivery-note/{n}">{n}</a>' for n in cancelled
				)),
				title=_("Return DNs Cancelled"),
				indicator="orange",
			)

	def on_submit(self):
		created = self._create_return_delivery_notes()
		self.db_set("created_return_dns", ", ".join(created))
		frappe.msgprint(
			_("Created {0} Return Delivery Note(s): {1}").format(
				len(created),
				", ".join(
					f'<a href="/app/delivery-note/{n}">{n}</a>' for n in created
				),
			),
			title=_("Return DNs Created"),
		)

	def _create_return_delivery_notes(self):
		from erpnext.controllers.sales_and_purchase_return import make_return_doc

		# Group items by source DN
		dn_groups: dict[str, dict] = {}
		for row in self.items:
			dn_groups.setdefault(row.against_delivery_note, {})[row.item_code] = (
				dn_groups.get(row.against_delivery_note, {}).get(row.item_code, 0)
				+ flt(row.qty)
			)

		created = []
		for source_dn, items_map in dn_groups.items():
			return_dn = make_return_doc("Delivery Note", source_dn)

			# Keep only items being returned in this group
			return_dn.items = [
				r for r in return_dn.items if r.item_code in items_map
			]

			for row in return_dn.items:
				row.qty = -abs(items_map[row.item_code])
				row.stock_qty = row.qty * (flt(row.conversion_factor) or 1)
				# Per-row warehouse override
				drr_row = next(
					(r for r in self.items
					 if r.item_code == row.item_code
					 and r.against_delivery_note == source_dn),
					None,
				)
				if drr_row and drr_row.warehouse:
					row.warehouse = drr_row.warehouse
				elif self.warehouse:
					row.warehouse = self.warehouse

			# Posting date/time — honour backdated entries
			return_dn.set_posting_time = 1
			return_dn.posting_date = self.posting_date
			if self.posting_time:
				return_dn.posting_time = self.posting_time

			# Accounting dimensions
			if self.branch:
				return_dn.branch = self.branch
			if self.cost_center:
				return_dn.cost_center = self.cost_center
			if self.warehouse:
				return_dn.set_warehouse = self.warehouse

			return_dn.insert(ignore_permissions=True)
			return_dn.submit()
			created.append(return_dn.name)

		return created
