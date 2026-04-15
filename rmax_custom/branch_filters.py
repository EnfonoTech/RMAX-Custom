"""
Branch-based document filtering.

Restricts list views so branch users only see documents
linked to their branch's warehouses.
Uses permission_query_conditions hook.
"""

import frappe


def _is_branch_configured_user(user):
    """Check if user exists in any Branch Configuration."""
    return frappe.db.exists("Branch Configuration User", {"user": user})


def get_branch_warehouse_condition(user=None):
    """
    Return list of warehouses from the user's Branch Configuration(s).
    Uses Branch Configuration as source of truth (not User Permissions or roles).
    Returns empty string for Admin/Stock Manager (no restriction).
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Stock Manager" in roles:
        return ""

    # Check if user is in any Branch Configuration (source of truth)
    # Don't rely on Branch User role — it might not be assigned yet
    branch_configs = frappe.get_all(
        "Branch Configuration User",
        filters={"user": user},
        pluck="parent",
    )

    if not branch_configs:
        # User is NOT in any branch config — no filtering needed
        # (they get normal Frappe permission behavior)
        return ""

    # Get warehouses from those branch configurations
    warehouses = frappe.get_all(
        "Branch Configuration Warehouse",
        filters={"parent": ["in", branch_configs]},
        pluck="warehouse",
    )

    if not warehouses:
        return ""

    return list(set(warehouses))  # deduplicate


def si_permission_query(user):
    """Filter Sales Invoices by branch warehouse (via items or set_warehouse)."""
    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabSales Invoice`.`set_warehouse` IN ({wh_list})
        OR `tabSales Invoice`.`name` IN (
            SELECT DISTINCT parent FROM `tabSales Invoice Item`
            WHERE warehouse IN ({wh_list})
        )
        OR `tabSales Invoice`.`owner` = {frappe.db.escape(user)}
    )"""


def pi_permission_query(user):
    """Filter Purchase Invoices by branch warehouse."""
    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabPurchase Invoice`.`set_warehouse` IN ({wh_list})
        OR `tabPurchase Invoice`.`name` IN (
            SELECT DISTINCT parent FROM `tabPurchase Invoice Item`
            WHERE warehouse IN ({wh_list})
        )
        OR `tabPurchase Invoice`.`owner` = {frappe.db.escape(user)}
    )"""


def dn_permission_query(user):
    """Filter Delivery Notes by branch warehouse."""
    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabDelivery Note`.`set_warehouse` IN ({wh_list})
        OR `tabDelivery Note`.`name` IN (
            SELECT DISTINCT parent FROM `tabDelivery Note Item`
            WHERE warehouse IN ({wh_list})
        )
        OR `tabDelivery Note`.`owner` = {frappe.db.escape(user)}
    )"""


def pr_permission_query(user):
    """Filter Purchase Receipts by branch warehouse."""
    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabPurchase Receipt`.`set_warehouse` IN ({wh_list})
        OR `tabPurchase Receipt`.`name` IN (
            SELECT DISTINCT parent FROM `tabPurchase Receipt Item`
            WHERE warehouse IN ({wh_list})
        )
        OR `tabPurchase Receipt`.`owner` = {frappe.db.escape(user)}
    )"""


def pe_permission_query(user):
    """Filter Payment Entries — show those created by the user
    OR linked to Sales Invoices the user can see (via branch warehouse)."""
    if not user or user == "Administrator":
        return ""

    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Stock Manager" in roles:
        return ""

    if not _is_branch_configured_user(user):
        return ""

    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return f"""`tabPayment Entry`.`owner` = {frappe.db.escape(user)}"""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabPayment Entry`.`owner` = {frappe.db.escape(user)}
        OR `tabPayment Entry`.`name` IN (
            SELECT DISTINCT per.parent
            FROM `tabPayment Entry Reference` per
            INNER JOIN `tabSales Invoice Item` sii ON sii.parent = per.reference_name
            WHERE per.reference_doctype = 'Sales Invoice'
            AND sii.warehouse IN ({wh_list})
        )
    )"""


def quotation_permission_query(user):
    """Filter Quotations — show only those created by the user."""
    if not user or user == "Administrator":
        return ""

    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Stock Manager" in roles:
        return ""

    if not _is_branch_configured_user(user):
        return ""

    return f"""`tabQuotation`.`owner` = {frappe.db.escape(user)}"""


def stock_transfer_permission_query(user):
    """Filter Stock Transfers — show where source OR target warehouse matches user's branch."""
    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabStock Transfer`.`set_source_warehouse` IN ({wh_list})
        OR `tabStock Transfer`.`set_target_warehouse` IN ({wh_list})
        OR `tabStock Transfer`.`owner` = {frappe.db.escape(user)}
    )"""


def material_request_permission_query(user):
    """Filter Material Requests — show where source OR target warehouse matches user's branch."""
    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabMaterial Request`.`set_warehouse` IN ({wh_list})
        OR `tabMaterial Request`.`set_from_warehouse` IN ({wh_list})
        OR `tabMaterial Request`.`owner` = {frappe.db.escape(user)}
    )"""


def damage_slip_permission_query(user):
    """Filter Damage Slips by branch warehouse."""
    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabDamage Slip`.`branch_warehouse` IN ({wh_list})
        OR `tabDamage Slip`.`owner` = {frappe.db.escape(user)}
    )"""


def damage_transfer_permission_query(user):
    """Filter Damage Transfers by branch warehouse.
    Damage Users should see all transfers (they work at warehouse level)."""
    if not user or user == "Administrator":
        return ""

    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Stock Manager" in roles:
        return ""

    # Damage Users see all (they inspect transfers from any branch)
    if "Damage User" in roles:
        return ""

    warehouses = get_branch_warehouse_condition(user)
    if not warehouses:
        return ""

    wh_list = ", ".join(frappe.db.escape(w) for w in warehouses)

    return f"""(
        `tabDamage Transfer`.`branch_warehouse` IN ({wh_list})
        OR `tabDamage Transfer`.`owner` = {frappe.db.escape(user)}
    )"""
