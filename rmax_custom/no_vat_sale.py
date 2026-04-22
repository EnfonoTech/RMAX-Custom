# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""Setup helpers for the No VAT Sale workflow.

Runs from after_migrate. Ships the dedicated 'No VAT Price' price list
and keeps it idempotent so client edits survive upgrades.
"""

import frappe

NO_VAT_PRICE_LIST = "No VAT Price"


def setup_no_vat_sale():
	if frappe.db.exists("Price List", NO_VAT_PRICE_LIST):
		return
	try:
		frappe.get_doc({
			"doctype": "Price List",
			"price_list_name": NO_VAT_PRICE_LIST,
			"currency": frappe.db.get_single_value("Global Defaults", "default_currency") or "SAR",
			"enabled": 1,
			"buying": 0,
			"selling": 1,
		}).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"rmax_custom: failed to create No VAT Price list",
		)
