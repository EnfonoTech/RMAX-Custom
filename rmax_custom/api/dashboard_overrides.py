"""Dashboard data overrides to add connections between DocTypes."""

from frappe import _


def material_request_dashboard(data):
    """Add Stock Transfer connection to Material Request dashboard."""
    data["non_standard_fieldnames"] = data.get("non_standard_fieldnames", {})
    data["non_standard_fieldnames"]["Stock Transfer"] = "material_request"

    # Add to transactions
    data.setdefault("transactions", [])
    data["transactions"].append({
        "label": _("Stock Transfer"),
        "items": ["Stock Transfer"],
    })

    return data


def stock_transfer_dashboard(data):
    """Add Material Request connection to Stock Transfer dashboard."""
    data["fieldname"] = "material_request"

    data.setdefault("transactions", [])
    data["transactions"].append({
        "label": _("Reference"),
        "items": ["Material Request"],
    })

    return data
