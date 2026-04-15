# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

import frappe
from rmax_custom.branch_filters import get_branch_warehouse_condition


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150,
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200,
        },
    ]

    # Add a column for each selling Price List
    price_lists = get_selling_price_lists()
    for pl in price_lists:
        columns.append(
            {
                "label": pl,
                "fieldname": frappe.scrub(pl),
                "fieldtype": "Currency",
                "width": 120,
            }
        )

    columns.append(
        {
            "label": "Balance Qty",
            "fieldname": "balance_qty",
            "fieldtype": "Float",
            "width": 120,
        }
    )

    return columns


def get_selling_price_lists():
    """Return names of all enabled selling Price Lists.
    For restricted users (Branch User / Stock User), exclude buying and inter-company lists.
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)

    is_restricted = (
        "Branch User" in roles or "Stock User" in roles or "Damage User" in roles
    ) and "System Manager" not in roles and "Stock Manager" not in roles

    filters = {"selling": 1, "enabled": 1}
    if is_restricted:
        # Exclude buying-only price lists and inter-company lists
        filters["buying"] = 0

    price_lists = frappe.get_all(
        "Price List",
        filters=filters,
        pluck="name",
        order_by="name asc",
    )

    if is_restricted:
        # Also exclude price lists with "Inter" or "Buying" in name
        price_lists = [
            pl for pl in price_lists
            if "inter" not in pl.lower() and "buying" not in pl.lower()
        ]

    return price_lists


def get_data(filters):
    conditions = get_conditions(filters)
    warehouse_condition = get_warehouse_filter(filters)

    items = frappe.db.sql(
        """
        SELECT
            item.item_code,
            item.item_name
        FROM `tabItem` item
        WHERE item.disabled = 0
            AND item.is_stock_item = 1
            {conditions}
        ORDER BY item.item_code ASC
        """.format(conditions=conditions),
        as_dict=True,
    )

    if not items:
        return []

    price_lists = get_selling_price_lists()
    item_codes = [d.item_code for d in items]

    # Fetch prices for all items x price lists in one query
    prices = {}
    if price_lists:
        price_data = frappe.db.sql(
            """
            SELECT item_code, price_list, price_list_rate
            FROM `tabItem Price`
            WHERE item_code IN %(item_codes)s
                AND price_list IN %(price_lists)s
                AND selling = 1
            ORDER BY valid_from DESC
            """,
            {"item_codes": item_codes, "price_lists": price_lists},
            as_dict=True,
        )
        for p in price_data:
            key = (p.item_code, p.price_list)
            if key not in prices:
                prices[key] = p.price_list_rate

    # Fetch balance qty from Bin table
    balance_data = {}
    if warehouse_condition:
        bin_data = frappe.db.sql(
            """
            SELECT item_code, SUM(actual_qty) as balance_qty
            FROM `tabBin`
            WHERE item_code IN %(item_codes)s
                AND warehouse IN %(warehouses)s
            GROUP BY item_code
            """,
            {"item_codes": item_codes, "warehouses": warehouse_condition},
            as_dict=True,
        )
        for b in bin_data:
            balance_data[b.item_code] = b.balance_qty
    else:
        # No warehouse filter — show all stock
        bin_data = frappe.db.sql(
            """
            SELECT item_code, SUM(actual_qty) as balance_qty
            FROM `tabBin`
            WHERE item_code IN %(item_codes)s
            GROUP BY item_code
            """,
            {"item_codes": item_codes},
            as_dict=True,
        )
        for b in bin_data:
            balance_data[b.item_code] = b.balance_qty

    # Build result rows
    data = []
    for item in items:
        row = {
            "item_code": item.item_code,
            "item_name": item.item_name,
        }
        for pl in price_lists:
            row[frappe.scrub(pl)] = prices.get((item.item_code, pl), 0)

        row["balance_qty"] = balance_data.get(item.item_code, 0)
        data.append(row)

    return data


def get_conditions(filters):
    conditions = ""
    if filters.get("company"):
        conditions += " AND EXISTS (SELECT 1 FROM `tabItem Default` id WHERE id.parent = item.name AND id.company = %(company)s)"
    if filters.get("item_group"):
        conditions += " AND item.item_group = %(item_group)s"
    return conditions % {
        "company": frappe.db.escape(filters.get("company", "")),
        "item_group": frappe.db.escape(filters.get("item_group", "")),
    } if conditions else ""


def get_warehouse_filter(filters):
    """Return list of warehouses to filter Bin by."""
    if filters.get("warehouse"):
        return [filters.get("warehouse")]

    # Use branch warehouses for branch users
    warehouses = get_branch_warehouse_condition()
    if warehouses:
        return warehouses

    return []
