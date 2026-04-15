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
    # Page DocType — needed for rmax-dashboard custom page
    {"parent": "Page", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # Stock report support doctypes (read-only, needed for Stock Balance/Ledger reports)
    {"parent": "UOM", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Item Group", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Brand", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Item Price", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
]


STOCK_USER_ROLE = "Stock User"

# Extra permissions for Stock User (only what ERPNext doesn't provide by default)
STOCK_USER_EXTRA_PERMISSIONS = [
    {"parent": "Item Price", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "UOM", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Item Group", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Brand", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
]

# Reports that Branch User / Stock User need access to
REPORT_ROLE_GRANTS = [
    {"report": "General Ledger", "roles": [BRANCH_USER_ROLE, STOCK_USER_ROLE]},
    {"report": "Stock Balance", "roles": [BRANCH_USER_ROLE, STOCK_USER_ROLE]},
    {"report": "Stock Ledger", "roles": [BRANCH_USER_ROLE, STOCK_USER_ROLE]},
]

BRANCH_USER_ALLOWED_MODULES = [
    "Rmax Custom",
    "Desk", "Core", "Workflow", "Printing", "Contacts", "Communication",
]


def after_migrate():
    """Set up Branch User role permissions after migration."""
    setup_branch_user_permissions()
    setup_stock_user_extra_permissions()
    setup_report_role_grants()
    setup_branch_user_module_profile()
    restrict_core_workspaces()
    setup_role_home_pages()


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


def setup_stock_user_extra_permissions():
    """Create Custom DocPerm records for Stock User (only missing ones)."""
    if not frappe.db.exists("Role", STOCK_USER_ROLE):
        return

    for perm in STOCK_USER_EXTRA_PERMISSIONS:
        doctype = perm["parent"]

        existing = frappe.db.exists("Custom DocPerm", {
            "parent": doctype,
            "role": STOCK_USER_ROLE,
            "permlevel": 0,
        })

        if existing:
            frappe.db.set_value("Custom DocPerm", existing, {
                k: v for k, v in perm.items() if k != "parent"
            })
        else:
            doc = frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": STOCK_USER_ROLE,
                "permlevel": 0,
                **{k: v for k, v in perm.items() if k != "parent"},
            })
            doc.insert(ignore_permissions=True)

    frappe.db.commit()


def setup_report_role_grants():
    """Add Branch User / Stock User roles to reports (e.g. General Ledger).

    ERPNext reports restrict access via Has Role entries on the Report doc.
    We add our roles without removing existing ones.
    """
    for grant in REPORT_ROLE_GRANTS:
        report_name = grant["report"]
        if not frappe.db.exists("Report", report_name):
            continue

        for role in grant["roles"]:
            if not frappe.db.exists("Role", role):
                continue

            # Check if role already granted
            exists = frappe.db.exists("Has Role", {
                "parent": report_name,
                "parenttype": "Report",
                "role": role,
            })
            if not exists:
                frappe.get_doc({
                    "doctype": "Has Role",
                    "parent": report_name,
                    "parenttype": "Report",
                    "parentfield": "roles",
                    "role": role,
                }).insert(ignore_permissions=True)

    frappe.db.commit()


def setup_branch_user_module_profile():
    """Create/update 'Branch User' Module Profile and sync block_modules on all users.

    This is the SINGLE SOURCE OF TRUTH for Branch User module restrictions.
    On a fresh site, `bench migrate` calls this and everything is configured
    automatically — no manual steps needed.
    """
    all_modules = frappe.get_all("Module Def", pluck="name")
    blocked_modules = [m for m in all_modules if m not in BRANCH_USER_ALLOWED_MODULES]

    # 1. Create/update the Module Profile using DIRECT DB to avoid
    #    on_update → queue_action → DocumentLockedError during migrate.
    if not frappe.db.exists("Module Profile", "Branch User"):
        frappe.db.sql(
            "INSERT INTO `tabModule Profile` (name, module_profile_name, owner, creation, modified, modified_by, docstatus)"
            " VALUES ('Branch User', 'Branch User', 'Administrator', NOW(), NOW(), 'Administrator', 0)"
        )

    # Clear existing block_modules
    frappe.db.delete("Block Module", {"parent": "Branch User", "parenttype": "Module Profile"})

    # Insert blocked modules
    for mod in blocked_modules:
        frappe.get_doc({
            "doctype": "Block Module",
            "parent": "Branch User",
            "parenttype": "Module Profile",
            "parentfield": "block_modules",
            "module": mod,
        }).db_insert()

    # 2. Apply profile + sync block_modules on every Branch User
    #    Uses direct DB to avoid user.save() failures (password validation etc.)
    branch_users = frappe.get_all(
        "Branch Configuration User",
        fields=["user", "role"],
        distinct=True,
    )
    for row in branch_users:
        user_email = row.user
        user_role = row.get("role") or BRANCH_USER_ROLE

        if user_role != BRANCH_USER_ROLE:
            continue
        if not frappe.db.exists("User", user_email):
            continue

        # Set module_profile on user (direct DB — no validation)
        frappe.db.set_value("User", user_email, "module_profile", "Branch User")

        # Sync block_modules child table
        # Clear existing
        frappe.db.delete("Block Module", {"parent": user_email, "parenttype": "User"})
        # Insert blocked modules
        for mod in blocked_modules:
            frappe.get_doc({
                "doctype": "Block Module",
                "parent": user_email,
                "parenttype": "User",
                "parentfield": "block_modules",
                "module": mod,
            }).insert(ignore_permissions=True)

    frappe.db.commit()


# Frappe core workspaces that should be restricted to System Manager
RESTRICTED_WORKSPACES = {
    "Users": ["System Manager"],
}


def restrict_core_workspaces():
    """Set roles on Frappe core workspaces so they don't show for Branch Users.

    The 'Users' workspace is under Core module (which we allow for basic
    desk functionality) but should only be visible to System Manager.
    """
    for ws_name, allowed_roles in RESTRICTED_WORKSPACES.items():
        if not frappe.db.exists("Workspace", ws_name):
            continue

        # Clear existing roles for this workspace
        frappe.db.delete(
            "Has Role",
            {"parent": ws_name, "parenttype": "Workspace"},
        )

        # Insert allowed roles
        for role in allowed_roles:
            frappe.get_doc({
                "doctype": "Has Role",
                "parent": ws_name,
                "parenttype": "Workspace",
                "parentfield": "roles",
                "role": role,
            }).insert(ignore_permissions=True)

    frappe.db.commit()


# Role home pages — Frappe uses Role.home_page to determine redirect after login
ROLE_HOME_PAGES = {
    "Branch User": "rmax-dashboard",
}


def setup_role_home_pages():
    """Set home_page on roles so users land on the correct page after login.

    Frappe checks Role.home_page during get_home_page() and redirects
    accordingly. This is the proper Frappe mechanism — no JS hacks needed.
    """
    for role_name, home_page in ROLE_HOME_PAGES.items():
        if frappe.db.exists("Role", role_name):
            frappe.db.set_value("Role", role_name, "home_page", home_page)

    frappe.db.commit()
