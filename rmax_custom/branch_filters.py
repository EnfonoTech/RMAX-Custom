"""
Branch-based document filtering.

Restricts list views so branch users only see documents
linked to their branch's warehouses.
Uses permission_query_conditions hook.
"""

import frappe


def get_branch_warehouse_condition(user=None):
    """
    Return SQL condition to filter documents by the user's branch warehouses.
    Used for doctypes that have items with a warehouse field (SI, PI, DN, PR).
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

    # Get user's permitted warehouses
    warehouses = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Warehouse"},
        pluck="for_value",
    )

    if not warehouses:
        return ""

    return warehouses


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
