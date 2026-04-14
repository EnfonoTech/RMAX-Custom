"""
Branch-based document filtering.

Restricts list views so branch users only see documents
linked to their branch's warehouses.
Uses permission_query_conditions hook.
"""

import frappe


def get_branch_warehouse_condition(user=None):
    """
    Return list of warehouses from the user's Branch Configuration(s).
    Uses Branch Configuration as source of truth (not User Permissions).
    Returns empty string for Admin/Stock Manager (no restriction).
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Stock Manager" in roles:
        return ""

    if "Branch User" not in roles:
        return ""

    # Get user's branch configurations
    branch_configs = frappe.get_all(
        "Branch Configuration User",
        filters={"user": user},
        pluck="parent",
    )

    if not branch_configs:
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
    """Filter Payment Entries — show only those created by the user or for their company."""
    if not user or user == "Administrator":
        return ""

    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Stock Manager" in roles:
        return ""

    if "Branch User" not in roles:
        return ""

    return f"""`tabPayment Entry`.`owner` = {frappe.db.escape(user)}"""


def quotation_permission_query(user):
    """Filter Quotations — show only those created by the user."""
    if not user or user == "Administrator":
        return ""

    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Stock Manager" in roles:
        return ""

    if "Branch User" not in roles:
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
        OR `tabMaterial Request`.`name` IN (
            SELECT DISTINCT parent FROM `tabMaterial Request Item`
            WHERE (warehouse IN ({wh_list}) OR from_warehouse IN ({wh_list}))
        )
        OR `tabMaterial Request`.`owner` = {frappe.db.escape(user)}
    )"""
