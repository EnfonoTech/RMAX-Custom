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

    is_restricted = "Branch User" in roles or "Stock User" in roles

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
