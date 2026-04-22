# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LCVChargeTemplate(Document):
	def validate(self):
		if self.is_default:
			# Only one default at a time
			others = frappe.get_all(
				"LCV Charge Template",
				filters={"is_default": 1, "name": ["!=", self.name]},
				pluck="name",
			)
			for other in others:
				frappe.db.set_value("LCV Charge Template", other, "is_default", 0)
