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
    """Show Material Request in Stock Transfer connections.
    We don't set fieldname or internal_links here — the MR side already
    uses non_standard_fieldnames to find STs. On the ST form itself, the
    material_request Link field in the Reference section is enough for
    users to navigate to the MR.
    """
    return data
