"""Dashboard data overrides to add connections between DocTypes."""

from frappe import _


def material_request_dashboard(data):
    """Add Stock Transfer connection to Material Request dashboard.
    Stock Transfer has a 'material_request' Link field pointing to Material Request,
    so we use non_standard_fieldnames to tell Frappe which field to look up.
    """
    data["non_standard_fieldnames"] = data.get("non_standard_fieldnames", {})
    data["non_standard_fieldnames"]["Stock Transfer"] = "material_request"

    data.setdefault("transactions", [])
    data["transactions"].append({
        "label": _("Fulfillment"),
        "items": ["Stock Transfer"],
    })

    return data


def stock_transfer_dashboard(data):
    """Add Material Request connection to Stock Transfer dashboard.
    Stock Transfer itself has the 'material_request' field (internal link),
    so we use internal_links to show the referenced MR in connections.
    """
    data.setdefault("internal_links", {})
    data["internal_links"]["Material Request"] = "material_request"

    data.setdefault("transactions", [])
    data["transactions"].append({
        "label": _("Reference"),
        "items": ["Material Request"],
    })

    return data
