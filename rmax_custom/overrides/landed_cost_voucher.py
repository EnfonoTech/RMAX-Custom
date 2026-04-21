# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.meta import get_field_precision
from frappe.utils import flt

from erpnext.stock.doctype.landed_cost_voucher.landed_cost_voucher import LandedCostVoucher as ERPNextLandedCostVoucher

from rmax_custom.landed_cost import get_based_on_field


class LandedCostVoucher(ERPNextLandedCostVoucher):
	def set_applicable_charges_on_item(self):
		if not self.get("taxes"):
			return
		# Distribute Manually + Distribute by CBM: use custom_cbm ratio
		if self.distribute_charges_based_on == "Distribute Manually" and self.get("custom_distribute_by_cbm"):
			self._set_applicable_charges_based_on_cbm()
			return
		if self.distribute_charges_based_on == "Distribute Manually":
			return
		# Qty or Amount
		total_item_cost = 0.0
		total_charges = 0.0
		item_count = 0
		based_on_field = get_based_on_field(self.distribute_charges_based_on)

		for item in self.get("items"):
			total_item_cost += flt(item.get(based_on_field))

		for item in self.get("items"):
			if not total_item_cost and not item.get(based_on_field):
				frappe.throw(
					_(
						"It's not possible to distribute charges equally when total is zero. "
						"Please enter values for all items or change 'Distribute Charges Based On'."
					)
				)

			item.applicable_charges = flt(
				flt(item.get(based_on_field))
				* (flt(self.total_taxes_and_charges) / flt(total_item_cost)),
				item.precision("applicable_charges"),
			)
			total_charges += item.applicable_charges
			item_count += 1

		if total_charges != self.total_taxes_and_charges:
			diff = self.total_taxes_and_charges - total_charges
			self.get("items")[item_count - 1].applicable_charges += diff

	def _set_applicable_charges_based_on_cbm(self):
		"""Distribute charges by custom_cbm ratio (when Distribute Manually + Distribute by CBM)."""
		based_on_field = "custom_cbm"
		total_item_cost = 0.0
		for item in self.get("items"):
			total_item_cost += flt(item.get(based_on_field))
		if not total_item_cost:
			for item in self.get("items"):
				item.applicable_charges = 0
			return
		total_charges = 0.0
		item_count = 0
		for item in self.get("items"):
			item.applicable_charges = flt(
				flt(item.get(based_on_field))
				* (flt(self.total_taxes_and_charges) / flt(total_item_cost)),
				item.precision("applicable_charges"),
			)
			total_charges += item.applicable_charges
			item_count += 1
		if total_charges != self.total_taxes_and_charges and item_count:
			diff = self.total_taxes_and_charges - total_charges
			self.get("items")[item_count - 1].applicable_charges += diff

	def validate_applicable_charges_for_item(self):
		is_cbm = (
			self.distribute_charges_based_on == "Distribute Manually"
			and self.get("custom_distribute_by_cbm")
		)

		if (
			self.distribute_charges_based_on == "Distribute Manually"
			and not is_cbm
			and len(self.taxes) > 1
		):
			frappe.throw(
				_(
					"Please keep one Applicable Charges, when 'Distribute Charges Based On' is 'Distribute Manually'. For more charges, please create another Landed Cost Voucher."
				)
			)

		based_on_field = get_based_on_field(self.distribute_charges_based_on)

		if is_cbm:
			total = sum(flt(d.get("custom_cbm")) for d in self.get("items"))
		elif self.distribute_charges_based_on != "Distribute Manually":
			total = sum(flt(d.get(based_on_field)) for d in self.get("items"))
		else:
			total = sum(flt(d.get("applicable_charges")) for d in self.get("items"))

		if not total:
			frappe.throw(
				_(
					"Total {0} for all items is zero, may be you should change 'Distribute Charges Based On'"
				).format(self.distribute_charges_based_on)
			)

		total_applicable_charges = sum(flt(d.applicable_charges) for d in self.get("items"))

		precision = get_field_precision(
			frappe.get_meta("Landed Cost Item").get_field("applicable_charges"),
			currency=frappe.get_cached_value("Company", self.company, "default_currency"),
		)

		diff = flt(self.total_taxes_and_charges) - flt(total_applicable_charges)
		diff = flt(diff, precision)

		if abs(diff) < (2.0 / (10**precision)):
			self.items[-1].applicable_charges += diff
		else:
			frappe.throw(
				_(
					"Total Applicable Charges in Purchase Receipt Items table must be same as Total Taxes and Charges"
				)
			)
