import frappe


def boot_session(bootinfo):
    """Override boot session to set Branch User / Stock User restrictions."""
    user = frappe.session.user
    if user == "Administrator" or user == "Guest":
        return

    roles = frappe.get_roles(user)

    # Skip admins
    if "System Manager" in roles or "Stock Manager" in roles:
        return

    is_restricted = (
        "Branch User" in roles
        or "Stock User" in roles
        or "Damage User" in roles
    )

    if is_restricted:
        # Force default route to rmax-dashboard
        bootinfo.default_route = "rmax-dashboard"

        # Only allow Rmax Custom module workspaces in sidebar
        bootinfo.allowed_modules = ["Rmax Custom"]

        # Only show the relevant workspace
        bootinfo.allowed_workspaces = [
            {"name": "Branch User"},
        ]

        # Add flag for JS to use
        bootinfo.is_branch_user_restricted = True

        # Set user's default company so forms don't pick up the wrong global default
        # (Global Defaults may be set to a company the user can't access, e.g. "RMAX")
        user_company = frappe.db.get_value(
            "User Permission",
            {"user": user, "allow": "Company", "is_default": 1},
            "for_value",
        )
        if user_company:
            bootinfo.user_default_company = user_company
            # Override sysdefaults so frappe.defaults.get_default("company") returns correct value
            if bootinfo.sysdefaults:
                bootinfo.sysdefaults["company"] = user_company
