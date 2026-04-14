"""
Override cost center on document tax rows and items with the user's
default cost center from Branch Configuration.

This prevents "Not Permitted" errors when the tax template has a cost center
(e.g. "Main - CNC") that the branch user doesn't have access to.

Also sets the cost_center on the document header and items if not already set.
"""

import frappe
from frappe.utils import cint


def override_cost_center_from_branch(doc, method=None):
    """Before validate: replace cost center with user's default if they don't have access."""
    if frappe.session.user == "Administrator":
        return

    user_cost_center = _get_user_default_cost_center()
    if not user_cost_center:
        return

    # Check if user has permission for the current cost center
    # If not, override with their default
    company = doc.company

    # Override document-level cost center
    if doc.get("cost_center"):
        if not _user_has_cost_center_access(doc.cost_center):
            doc.cost_center = user_cost_center
    else:
        doc.cost_center = user_cost_center

    # Override item-level cost centers
    for item in doc.get("items") or []:
        if hasattr(item, "cost_center"):
            if item.cost_center and not _user_has_cost_center_access(item.cost_center):
                item.cost_center = user_cost_center
            elif not item.cost_center:
                item.cost_center = user_cost_center

    # Override tax-level cost centers
    for tax in doc.get("taxes") or []:
        if hasattr(tax, "cost_center"):
            if tax.cost_center and not _user_has_cost_center_access(tax.cost_center):
                tax.cost_center = user_cost_center
            elif not tax.cost_center:
                tax.cost_center = user_cost_center


def _get_user_default_cost_center():
    """Get the user's default cost center from User Permission."""
    perm = frappe.db.get_value(
        "User Permission",
        {
            "user": frappe.session.user,
            "allow": "Cost Center",
            "is_default": 1,
        },
        "for_value",
    )
    return perm


def _user_has_cost_center_access(cost_center):
    """Check if user has User Permission for this cost center."""
    if not cost_center:
        return True

    return frappe.db.exists(
        "User Permission",
        {
            "user": frappe.session.user,
            "allow": "Cost Center",
            "for_value": cost_center,
        },
    )
