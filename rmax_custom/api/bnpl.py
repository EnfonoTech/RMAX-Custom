"""Whitelisted helpers for the BNPL surcharge flow."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt


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


@frappe.whitelist()
def get_clearing_account_for_mop(mop: str, company: str) -> dict:
	"""Resolve clearing account + currency for a (Mode of Payment, Company) pair.

	Returns: {"account": <account name or None>, "currency": <ccy or None>}.
	Used by the Journal Entry "Load BNPL Settlement" button on the client.
	"""
	if not (mop and company):
		return {"account": None, "currency": None}
	account = frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mop, "company": company},
		"default_account",
	)
	currency = (
		frappe.db.get_value("Account", account, "account_currency") if account else None
	)
	return {"account": account, "currency": currency}


@frappe.whitelist()
def get_clearing_balance(account: str) -> float:
	"""Live balance of an account (debit - credit across all GL entries).

	Used by the JE "Load BNPL Settlement" dialog to show the operator the
	current clearing balance before they fill in the credit amount.
	"""
	if not account or not frappe.db.exists("Account", account):
		return 0.0
	rows = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(IFNULL(debit, 0) - IFNULL(credit, 0)), 0) AS bal
		FROM `tabGL Entry`
		WHERE account = %(account)s AND IFNULL(is_cancelled, 0) = 0
		""",
		{"account": account},
		as_dict=True,
	)
	return flt(rows[0].bal) if rows else 0.0
