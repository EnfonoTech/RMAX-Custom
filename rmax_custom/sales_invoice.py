# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""Sales Invoice server-side hooks (validate / before_validate)."""

import frappe
from frappe import _


# Roles allowed to flip the Update Stock flag on Sales Invoice
UPDATE_STOCK_ALLOWED_ROLES = {
	"Sales Manager",
	"Sales Master Manager",
	"System Manager",
}


def _can_toggle_update_stock(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)) & UPDATE_STOCK_ALLOWED_ROLES)


def enforce_update_stock_permission(doc, method=None):
	"""Block non-managers from saving a Sales Invoice with Update Stock on.

	Runs via the Sales Invoice `validate` doc event. Branch Users default
	update_stock=0 via the client JS; this is the server-side safety net
	that also blocks API / frappe.client.save callers.
	"""
	if not doc.get("update_stock"):
		return

	if _can_toggle_update_stock():
		return

	frappe.throw(
		_("Only Sales Manager or above can enable 'Update Stock' on Sales Invoice."),
		title=_("Not Permitted"),
	)
