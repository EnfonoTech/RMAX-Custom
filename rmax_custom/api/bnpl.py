"""Whitelisted helpers for the BNPL surcharge flow."""

from __future__ import annotations

import json

import frappe
from frappe import _


@frappe.whitelist()
def set_pos_payments_snapshot(sales_invoice: str, payments_json):
	"""Persist the POS popup's payment-mode breakdown directly to the SI.

	The RMAX POS popup (sales_invoice_pos_total_popup.v2.js) calls this
	right before invoking ``frm.save()``. Writing the value via this API
	guarantees it lands in the DB even if Frappe's form-save serialiser
	drops the hidden field from the POST body (a common quirk for hidden
	custom fields on already-saved docs). The before_validate BNPL hook
	then reads the value back from the DB and applies the surcharge
	uplift.

	Returns the value that was stored, so the caller can verify.
	"""
	if not sales_invoice:
		frappe.throw(_("sales_invoice is required"))

	if isinstance(payments_json, (list, dict)):
		payload = json.dumps(payments_json)
	else:
		payload = payments_json or ""
		# Validate it parses
		if payload:
			try:
				json.loads(payload)
			except (TypeError, ValueError):
				frappe.throw(_("payments_json is not valid JSON"))

	if not frappe.db.exists("Sales Invoice", sales_invoice):
		frappe.throw(_("Sales Invoice {0} not found").format(sales_invoice))

	# Direct DB write so the value survives even if a subsequent form
	# save drops the field from its POST body.
	frappe.db.set_value(
		"Sales Invoice",
		sales_invoice,
		"custom_pos_payments_json",
		payload,
		update_modified=False,
	)
	frappe.db.commit()
	return payload
