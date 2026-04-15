import frappe


def boot_session(bootinfo):
    """Override boot session to set Branch User restrictions."""
    user = frappe.session.user
    if user == "Administrator" or user == "Guest":
        return

    roles = frappe.get_roles(user)

    # Skip admins
    if "System Manager" in roles or "Stock Manager" in roles:
        return

    if "Branch User" in roles:
        # Force default route to rmax-dashboard
        bootinfo.default_route = "rmax-dashboard"

        # Set allowed modules — hide everything else from sidebar
        bootinfo.allowed_modules = [
            "Selling",
            "Buying",
            "Stock",
            "Accounts",
        ]

        # Block workspaces — only allow the dashboard
        bootinfo.allowed_workspaces = []

        # Add flag for JS to use
        bootinfo.is_branch_user_restricted = True
