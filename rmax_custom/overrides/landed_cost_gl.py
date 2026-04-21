# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""Patched Landed Cost Voucher → Purchase Receipt GL distribution.

ERPNext stock.doctype.purchase_receipt.purchase_receipt.get_item_account_wise_additional_cost
cannot split per-item `applicable_charges` across multiple tax rows when
`distribute_charges_based_on == "Distribute Manually"`: each tax row adds the
full `applicable_charges` to its expense account, so Cr entries double.

RMAX allows multiple tax rows under Manual mode when CBM distribution is on
(see overrides.landed_cost_voucher.LandedCostVoucher). This override handles
the GL side by using `custom_cbm` as the distribution field when
`custom_distribute_by_cbm=1`, matching ERPNext's non-Manual path.

Installed via monkey patch in `rmax_custom/__init__.py` at import time.
"""

import frappe
from frappe.utils import flt


def get_item_account_wise_additional_cost(purchase_document):
	landed_cost_vouchers = frappe.get_all(
		"Landed Cost Purchase Receipt",
		fields=["parent"],
		filters={"receipt_document": purchase_document, "docstatus": 1},
	)

	if not landed_cost_vouchers:
		return

	item_account_wise_cost = {}

	for lcv in landed_cost_vouchers:
		landed_cost_voucher_doc = frappe.get_doc("Landed Cost Voucher", lcv.parent)

		based_on_field = None
		if (
			landed_cost_voucher_doc.distribute_charges_based_on == "Distribute Manually"
			and landed_cost_voucher_doc.get("custom_distribute_by_cbm")
		):
			based_on_field = "custom_cbm"
		elif landed_cost_voucher_doc.distribute_charges_based_on != "Distribute Manually":
			based_on_field = frappe.scrub(landed_cost_voucher_doc.distribute_charges_based_on)

		total_item_cost = 0
		if based_on_field:
			for item in landed_cost_voucher_doc.items:
				total_item_cost += flt(item.get(based_on_field))

		for item in landed_cost_voucher_doc.items:
			if item.receipt_document == purchase_document:
				for account in landed_cost_voucher_doc.taxes:
					exchange_rate = account.exchange_rate or 1
					key = (item.item_code, item.purchase_receipt_item)
					item_account_wise_cost.setdefault(key, {})
					item_account_wise_cost[key].setdefault(
						account.expense_account, {"amount": 0.0, "base_amount": 0.0}
					)

					item_row = item_account_wise_cost[key][account.expense_account]

					if total_item_cost > 0:
						item_row["amount"] += (
							account.amount * flt(item.get(based_on_field)) / total_item_cost
						)
						item_row["base_amount"] += (
							account.base_amount * flt(item.get(based_on_field)) / total_item_cost
						)
					else:
						item_row["amount"] += item.applicable_charges / exchange_rate
						item_row["base_amount"] += item.applicable_charges

	return item_account_wise_cost


def apply_patch():
	"""Monkey-patch the ERPNext module function."""
	from erpnext.stock.doctype.purchase_receipt import purchase_receipt as pr_mod

	pr_mod.get_item_account_wise_additional_cost = get_item_account_wise_additional_cost
