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
    """Show Inter-Branch companion JE in the Stock Transfer Connections sidebar.

    The Inter-Branch companion JE created by `Stock Transfer.on_submit` carries
    `custom_source_docname = ST.name` on its header (Phase 2). The dashboard
    looks up Journal Entries via that field.
    """
    data["non_standard_fieldnames"] = data.get("non_standard_fieldnames", {})
    data["non_standard_fieldnames"]["Journal Entry"] = "custom_source_docname"

    # Required so the JS set_open_count() guard (!this.data.fieldname) doesn't
    # short-circuit before fetching the badge count.
    data["fieldname"] = "custom_source_docname"

    # custom_source_docname is a Dynamic Link; the count query must also filter
    # by custom_source_doctype so it only counts JEs for this doctype.
    data["dynamic_links"] = data.get("dynamic_links", {})
    data["dynamic_links"]["custom_source_docname"] = ["Stock Transfer", "custom_source_doctype"]

    data.setdefault("transactions", [])
    data["transactions"].append({
        "label": _("Inter-Branch"),
        "items": ["Journal Entry"],
    })
    return data


def stock_entry_dashboard(data):
    """Show Inter-Branch companion JE on the Stock Entry Connections sidebar.

    Phase 2's `Stock Entry.on_submit` hook creates a Journal Entry with
    `custom_source_doctype = "Stock Entry"` and `custom_source_docname = SE.name`
    (header-level fields). Frappe's dashboard finder uses those to surface the JE.
    """
    data["non_standard_fieldnames"] = data.get("non_standard_fieldnames", {})
    data["non_standard_fieldnames"]["Journal Entry"] = "custom_source_docname"

    data["fieldname"] = "custom_source_docname"

    data["dynamic_links"] = data.get("dynamic_links", {})
    data["dynamic_links"]["custom_source_docname"] = ["Stock Entry", "custom_source_doctype"]

    data.setdefault("transactions", [])
    data["transactions"].append({
        "label": _("Inter-Branch"),
        "items": ["Journal Entry"],
    })
    return data
