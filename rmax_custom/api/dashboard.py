import frappe
from frappe import _


@frappe.whitelist()
def get_dashboard_data():
    """Return dashboard data based on user's role and branch."""
    user = frappe.session.user
    company = frappe.defaults.get_user_default("company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )

    # Determine user type
    roles = frappe.get_roles(user)
    is_branch_user = "Branch User" in roles
    is_stock_user = "Stock User" in roles
    is_admin = "System Manager" in roles or "Stock Manager" in roles

    # Get user's branch warehouses
    from rmax_custom.branch_filters import get_branch_warehouse_condition

    warehouses = get_branch_warehouse_condition(user) or []

    data = {
        "company": company,
        "is_branch_user": is_branch_user,
        "is_stock_user": is_stock_user,
        "is_admin": is_admin,
        "user": user,
        "warehouses": warehouses,
    }

    today = frappe.utils.today()
    first_of_month = frappe.utils.get_first_day(today)

    if is_branch_user or is_admin:
        # Build warehouse filter for branch users
        wh_filter = ""
        if warehouses and not is_admin:
            wh_list = ", ".join(f"'{frappe.db.escape(w)}'" for w in warehouses)
            wh_filter = f"AND si.set_warehouse IN ({wh_list})"

        # Daily sales
        data["daily_sales"] = (
            frappe.db.sql(
                f"""
                SELECT COALESCE(SUM(grand_total), 0)
                FROM `tabSales Invoice` si
                WHERE si.posting_date = %s AND si.docstatus = 1 {wh_filter}
            """,
                today,
            )[0][0]
            or 0
        )

        # Monthly sales
        data["monthly_sales"] = (
            frappe.db.sql(
                f"""
                SELECT COALESCE(SUM(grand_total), 0)
                FROM `tabSales Invoice` si
                WHERE si.posting_date >= %s AND si.posting_date <= %s
                AND si.docstatus = 1 {wh_filter}
            """,
                (first_of_month, today),
            )[0][0]
            or 0
        )

        # MTD invoice count
        data["mtd_invoices"] = (
            frappe.db.sql(
                f"""
                SELECT COUNT(*)
                FROM `tabSales Invoice` si
                WHERE si.posting_date >= %s AND si.docstatus = 1 {wh_filter}
            """,
                first_of_month,
            )[0][0]
            or 0
        )

        # Pending approvals (Stock Transfers waiting for approval)
        data["pending_approvals"] = frappe.db.count(
            "Stock Transfer", {"workflow_state": "Waiting for Approval"}
        )

        # Outstanding credits
        data["credits_outstanding"] = (
            frappe.db.sql(
                f"""
                SELECT COALESCE(SUM(outstanding_amount), 0)
                FROM `tabSales Invoice` si
                WHERE si.docstatus = 1 AND si.outstanding_amount > 0 {wh_filter}
            """
            )[0][0]
            or 0
        )

        # Pending stock transfers list
        st_filter = ""
        if warehouses and not is_admin:
            wh_list = ", ".join(f"'{frappe.db.escape(w)}'" for w in warehouses)
            st_filter = f"AND (set_source_warehouse IN ({wh_list}) OR set_target_warehouse IN ({wh_list}))"

        data["pending_transfers"] = frappe.db.sql(
            f"""
            SELECT name, set_source_warehouse, set_target_warehouse,
                   transaction_date, owner
            FROM `tabStock Transfer`
            WHERE workflow_state = 'Waiting for Approval' {st_filter}
            ORDER BY transaction_date DESC
            LIMIT 10
        """,
            as_dict=True,
        )

    if is_stock_user or is_admin:
        # Stock KPIs
        data["pending_mrs"] = frappe.db.count(
            "Material Request", {"status": "Pending", "docstatus": 1}
        )
        data["pending_sts"] = frappe.db.count(
            "Stock Transfer", {"workflow_state": "Waiting for Approval"}
        )
        data["total_items"] = frappe.db.count("Item", {"disabled": 0})

    data["currency"] = (
        frappe.db.get_value("Company", company, "default_currency") or "SAR"
    )

    return data
