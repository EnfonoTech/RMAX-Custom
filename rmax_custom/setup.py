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
    # Branch — HRMS locks this to HR roles only; Branch Users need read for No VAT Sale and other branch links.
    {"parent": "Branch", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    # No VAT Sale — create/submit gated at the doctype level by role permissions (only SM + Accounts Mgr can submit).
    {"parent": "No VAT Sale", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 0, "share": 0},
    # Settings doctypes (read-only, needed for opening PR/PI forms)
    {"parent": "Buying Settings", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Selling Settings", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Stock Settings", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # Territory, Customer Group — needed by Customer / Sales Invoice forms
    {"parent": "Territory", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Customer Group", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
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
    # User Permission — needed by Damage Slip/Transfer JS warehouse query
    {"parent": "User Permission", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # Warehouse Pick List — picking operations
    {"parent": "Warehouse Pick List", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 0, "share": 0},
    # Stock report support doctypes (read-only, needed for Stock Balance/Ledger reports)
    {"parent": "UOM", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Item Group", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Brand", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Item Price", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    # Damage workflow DocTypes
    {"parent": "Damage Slip", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Damage Transfer", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Supplier Code", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
]


STOCK_USER_ROLE = "Stock User"

# Extra permissions for Stock User (only what ERPNext doesn't provide by default)
STOCK_USER_EXTRA_PERMISSIONS = [
    {"parent": "Item Price", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "UOM", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Item Group", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Brand", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # Page DocType — needed for rmax-dashboard custom page
    {"parent": "Page", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # User Permission — needed by MR / Stock Transfer / Warehouse Pick List JS warehouse queries
    {"parent": "User Permission", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # Settings doctypes (read-only, needed for opening PR/PI forms)
    {"parent": "Buying Settings", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Selling Settings", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # Purchase Receipt — Stock Users need to create/submit PRs
    # (Custom DocPerm on Branch User replaced standard permissions, so Stock User needs explicit entry)
    {"parent": "Purchase Receipt", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 0},
    # Purchase Invoice — Stock Users need to create/submit PIs
    {"parent": "Purchase Invoice", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 1, "report": 1, "export": 1, "share": 0},
    # Support doctypes for Purchase Receipt / forms (read-only)
    {"parent": "Supplier", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Account", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Accounts Settings", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Cost Center", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Address", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Contact", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Customer", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # Material Request — Stock Users need to create MRs
    {"parent": "Material Request", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 0, "share": 0},
    # Stock Transfer — Stock Users need full access to create/edit/submit STs
    {"parent": "Stock Transfer", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 0, "share": 0},
    # Branch — needed for No VAT Sale form
    {"parent": "Branch", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    # No VAT Sale — Stock Users can draft (submit is gated)
    {"parent": "No VAT Sale", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 0, "share": 0},
    # Warehouse Pick List — picking operations
    {"parent": "Warehouse Pick List", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 0, "share": 0},
    # Damage workflow DocTypes
    {"parent": "Damage Slip", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Damage Transfer", "read": 1, "write": 1, "create": 0, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Supplier Code", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
]


DAMAGE_USER_ROLE = "Damage User"

# DocType permissions for Damage User
DAMAGE_USER_PERMISSIONS = [
    {"parent": "Damage Slip", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Damage Transfer", "read": 1, "write": 1, "create": 0, "submit": 1, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Supplier Code", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Item", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Warehouse", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 1, "export": 0, "share": 0},
    {"parent": "Company", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Stock Entry", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 1, "email": 0, "report": 1, "export": 1, "share": 0},
    {"parent": "Page", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "UOM", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Item Group", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Brand", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Account", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    # Support DocTypes needed by form JS (warehouse queries, customer references, etc.)
    {"parent": "User Permission", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Customer", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Supplier", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Cost Center", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Item Price", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Price List", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Address", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Contact", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
    {"parent": "Accounts Settings", "read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0, "print": 0, "email": 0, "report": 0, "export": 0, "share": 0},
]

# Purchase Manager permissions for Supplier Code master
PURCHASE_MANAGER_SUPPLIER_CODE_PERM = [
    {"parent": "Supplier Code", "read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 1, "print": 1, "email": 0, "report": 1, "export": 1, "share": 1},
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
    fix_stock_transfer_series()
    preserve_standard_docperms_on_touched_doctypes()
    setup_branch_user_permissions()
    setup_stock_user_extra_permissions()
    setup_damage_user_permissions()
    setup_purchase_manager_supplier_code()
    setup_vat_duplicate_override_perms()
    setup_report_role_grants()
    setup_branch_user_module_profile()
    setup_damage_user_module_profile()
    restrict_core_workspaces()
    setup_role_home_pages()

    # HR defaults (no-op if hrms not installed)
    try:
        from rmax_custom.hr_defaults import setup_hr_defaults

        setup_hr_defaults()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "rmax_custom: hr_defaults setup failed")

    # LCV Charge Template defaults (accounts + default template)
    try:
        from rmax_custom.lcv_template import setup_lcv_defaults

        setup_lcv_defaults()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "rmax_custom: lcv_template setup failed")

    # Inter Company Price list (for DN inter-company mode)
    try:
        from rmax_custom.inter_company_dn import setup_inter_company_price_list

        setup_inter_company_price_list()
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "rmax_custom: inter company price list setup failed",
        )

    # No VAT Sale price list
    try:
        from rmax_custom.no_vat_sale import setup_no_vat_sale

        setup_no_vat_sale()
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "rmax_custom: no vat sale setup failed",
        )

    # BNPL clearing + fee accounts (Tabby/Tamara)
    try:
        from rmax_custom.bnpl_settlement_setup import setup_bnpl_accounts

        setup_bnpl_accounts()
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "rmax_custom: bnpl_settlement_setup failed",
        )


# Roles allowed to tick custom_allow_duplicate_vat on Customer (permlevel 1)
VAT_DUPLICATE_OVERRIDE_ROLES = ("Sales Manager", "Sales Master Manager", "System Manager")


def setup_vat_duplicate_override_perms():
    """Grant permlevel=1 write on Customer to roles allowed to override VAT duplicate check."""
    if not frappe.db.exists("DocType", "Customer"):
        return

    for role in VAT_DUPLICATE_OVERRIDE_ROLES:
        if not frappe.db.exists("Role", role):
            continue

        existing = frappe.db.exists("Custom DocPerm", {
            "parent": "Customer",
            "role": role,
            "permlevel": 1,
        })

        if existing:
            frappe.db.set_value("Custom DocPerm", existing, {
                "read": 1,
                "write": 1,
            })
        else:
            frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": "Customer",
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": 1,
                "read": 1,
                "write": 1,
            }).insert(ignore_permissions=True)

    frappe.db.commit()


# DocPerm fields that need to be mirrored from standard DocPerm into Custom DocPerm.
# permlevel is set separately to normalize None → 0.
_DOCPERM_FLAGS = (
    "read", "write", "create", "submit", "cancel", "delete",
    "print", "email", "report", "export", "share",
    "if_owner", "amend", "select", "import",
)


def fix_stock_transfer_series():
    """Keep the Stock Transfer 'ST-' counter aligned with the highest
    existing ST-##### document name.

    The DocType autoname now uses the classic form 'ST-.#####', so the
    counter lives under name='ST-' in tabSeries. Earlier the autoname
    was 'format:{ST}-{#####}' which stored the counter under an empty
    name key, occasionally drifting below the real max and producing
    'Stock Transfer ST-XXXXX already exists' errors.

    This function:
    * finds the max ST-##### in tabStock Transfer,
    * copies the legacy empty-name counter forward (one-time migration),
    * ensures tabSeries has an 'ST-' row with current >= max.

    Safe and idempotent — only ever bumps the counter upward.
    """
    rows = frappe.db.sql(
        """SELECT name FROM `tabStock Transfer`
           WHERE name LIKE 'ST-%%' ORDER BY name DESC LIMIT 1""",
        as_dict=False,
    )
    current_max = 0
    if rows:
        try:
            current_max = int(rows[0][0].split("-")[-1])
        except Exception:
            current_max = 0

    # Legacy empty-name counter (from the old format:{ST}-{#####} days)
    legacy = frappe.db.sql(
        "SELECT current FROM tabSeries WHERE name = '' OR name IS NULL LIMIT 1",
        as_dict=False,
    )
    legacy_current = int(legacy[0][0]) if legacy and legacy[0][0] else 0

    target = max(current_max, legacy_current)
    if target <= 0:
        return

    existing = frappe.db.sql(
        "SELECT current FROM tabSeries WHERE name = 'ST-'",
        as_dict=False,
    )
    if existing:
        existing_current = int(existing[0][0] or 0)
        if existing_current < target:
            frappe.db.sql(
                "UPDATE tabSeries SET current = %s WHERE name = 'ST-'",
                (target,),
            )
    else:
        frappe.db.sql(
            "INSERT INTO tabSeries (name, current) VALUES ('ST-', %s)",
            (target,),
        )

    frappe.db.commit()


def preserve_standard_docperms_on_touched_doctypes():
    """Copy every standard DocPerm row into Custom DocPerm for doctypes we customize.

    Frappe replaces standard DocPerm with Custom DocPerm as soon as any Custom
    DocPerm row exists for a doctype. Without this backfill, adding Stock/Branch/
    Damage User perms wipes access for existing standard roles (e.g. Accounts
    Manager, Purchase User, Sales User on Accounts Settings).
    """
    rmax_roles = {BRANCH_USER_ROLE, STOCK_USER_ROLE, DAMAGE_USER_ROLE, "Stock Manager"}
    touched_doctypes = {p["parent"] for p in BRANCH_USER_PERMISSIONS}
    touched_doctypes |= {p["parent"] for p in STOCK_USER_EXTRA_PERMISSIONS}
    touched_doctypes |= {p["parent"] for p in DAMAGE_USER_PERMISSIONS}
    touched_doctypes |= {p["parent"] for p in PURCHASE_MANAGER_SUPPLIER_CODE_PERM}

    for doctype in touched_doctypes:
        if not frappe.db.exists("DocType", doctype):
            continue

        standard_rows = frappe.get_all(
            "DocPerm",
            filters={"parent": doctype, "parenttype": "DocType"},
            fields=["name", "role", "permlevel"] + list(_DOCPERM_FLAGS),
        )

        for row in standard_rows:
            role = row.get("role")
            if not role or role in rmax_roles:
                continue

            permlevel = row.get("permlevel") or 0

            existing = frappe.db.exists("Custom DocPerm", {
                "parent": doctype,
                "role": role,
                "permlevel": permlevel,
            })
            if existing:
                continue

            payload = {
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": permlevel,
            }
            for flag in _DOCPERM_FLAGS:
                val = row.get(flag)
                if val is None:
                    continue
                payload[flag] = val

            frappe.get_doc(payload).insert(ignore_permissions=True)

    frappe.db.commit()


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
    "Stock User": "rmax-dashboard",
    "Damage User": "rmax-dashboard",
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


def setup_damage_user_permissions():
    """Create Custom DocPerm records for Damage User role."""
    if not frappe.db.exists("Role", DAMAGE_USER_ROLE):
        return

    for perm in DAMAGE_USER_PERMISSIONS:
        doctype = perm["parent"]
        existing = frappe.db.exists("Custom DocPerm", {
            "parent": doctype,
            "role": DAMAGE_USER_ROLE,
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
                "role": DAMAGE_USER_ROLE,
                "permlevel": 0,
                **{k: v for k, v in perm.items() if k != "parent"},
            })
            doc.insert(ignore_permissions=True)

    frappe.db.commit()


def setup_purchase_manager_supplier_code():
    """Give Purchase Manager full control over Supplier Code."""
    role = "Purchase Manager"
    if not frappe.db.exists("Role", role):
        return

    for perm in PURCHASE_MANAGER_SUPPLIER_CODE_PERM:
        doctype = perm["parent"]
        existing = frappe.db.exists("Custom DocPerm", {
            "parent": doctype,
            "role": role,
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
                "role": role,
                "permlevel": 0,
                **{k: v for k, v in perm.items() if k != "parent"},
            })
            doc.insert(ignore_permissions=True)

    frappe.db.commit()


DAMAGE_USER_ALLOWED_MODULES = [
    "Rmax Custom",
    "Desk", "Core", "Workflow", "Printing",
]


def setup_damage_user_module_profile():
    """Create/update 'Damage User' Module Profile."""
    all_modules = frappe.get_all("Module Def", pluck="name")
    blocked_modules = [m for m in all_modules if m not in DAMAGE_USER_ALLOWED_MODULES]

    if not frappe.db.exists("Module Profile", "Damage User"):
        frappe.db.sql(
            "INSERT INTO `tabModule Profile` (name, module_profile_name, owner, creation, modified, modified_by, docstatus)"
            " VALUES ('Damage User', 'Damage User', 'Administrator', NOW(), NOW(), 'Administrator', 0)"
        )

    frappe.db.delete("Block Module", {"parent": "Damage User", "parenttype": "Module Profile"})

    for mod in blocked_modules:
        frappe.get_doc({
            "doctype": "Block Module",
            "parent": "Damage User",
            "parenttype": "Module Profile",
            "parentfield": "block_modules",
            "module": mod,
        }).db_insert()

    frappe.db.commit()
