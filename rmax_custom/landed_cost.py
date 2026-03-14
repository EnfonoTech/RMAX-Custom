# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""Landed Cost Voucher: get_based_on_field for Qty/Amount distribution."""

import frappe


def get_based_on_field(distribute_charges_based_on):
	"""Return the item field to use for distribution (Qty -> qty, Amount -> amount)."""
	return frappe.scrub(distribute_charges_based_on)
