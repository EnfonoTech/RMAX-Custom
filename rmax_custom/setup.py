"""
Post-migration setup: create Branch User role permissions.
Called via after_migrate hook.
"""

import frappe

BRANCH_USER_ROLE = "Branch User"

# DocType permissions for Branch User
BRANCH_USER_PERMISSIONS = [
    {"parent": "Sales Invoice", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Quotation", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Customer", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Payment Entry", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Purchase Receipt", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Delivery Note", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Purchase Invoice", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Stock Transfer", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Material Request", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Item", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Price List", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Address", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Contact", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 1},
    {"parent": "Stock Entry", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    # Accounting support doctypes (read-only, needed for SI/PE creation)
    {"parent": "Account", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Accounts Settings", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Mode of Payment", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Sales Taxes and Charges Template", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Payment Terms Template", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "POS Profile", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Cost Center", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Warehouse", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Company", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Supplier", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
]


def after_migrate():
    """Set up Branch User role permissions after migration."""
    setup_branch_user_permissions()


def setup_branch_user_permissions():
    """Create Custom DocPerm records for Branch User role."""
    if not frappe.db.exists("Role", BRANCH_USER_ROLE):
        return

    for perm in BRANCH_USER_PERMISSIONS:
        doctype = perm["parent"]

        # Check if permission already exists
        existing = frappe.db.exists("Custom DocPerm", {
            "parent": doctype,
            "role": BRANCH_USER_ROLE,
            "permlevel": 0,
        })

        if existing:
            # Update existing permission
            frappe.db.set_value("Custom DocPerm", existing, {
                "read": perm.get("read", 0),
                "write": perm.get("write", 0),
                "create": perm.get("create", 0),
                "submit": perm.get("submit", 0),
                "cancel": perm.get("cancel", 0),
                "delete": perm.get("delete", 0),
                "print": perm.get("print", 0),
                "email": perm.get("email", 0),
                "report": perm.get("report", 0),
                "export": perm.get("export", 0),
                "share": perm.get("share", 0),
            })
        else:
            doc = frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": BRANCH_USER_ROLE,
                "permlevel": 0,
                **{k: v for k, v in perm.items() if k != "parent"},
            })
            doc.insert(ignore_permissions=True)

    frappe.db.commit()
