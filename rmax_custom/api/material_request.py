import frappe
from frappe.utils import nowdate, flt, add_days
from frappe import _

@frappe.whitelist()
def create_material_request(item_code, from_warehouse, to_warehouse, qty, schedule_date, material_request_type, company):
    """Create a Material Request for Material Transfer."""
    
    if not item_code:
        frappe.throw(_("Item Code is required"))
    if not from_warehouse:
        frappe.throw(_("From Warehouse is required"))
    if not to_warehouse:
        frappe.throw(_("To Warehouse is required"))
    if from_warehouse == to_warehouse:
        frappe.throw(_("From Warehouse and To Warehouse cannot be the same"))
    if not qty or flt(qty) <= 0:
        frappe.throw(_("Quantity must be greater than 0"))
    if not company:
        frappe.throw(_("Company is required"))

    # Validate item exists
    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item {0} does not exist").format(item_code))

    # Validate warehouses exist
    if not frappe.db.exists("Warehouse", from_warehouse):
        frappe.throw(_("From Warehouse {0} does not exist").format(from_warehouse))
    if not frappe.db.exists("Warehouse", to_warehouse):
        frappe.throw(_("To Warehouse {0} does not exist").format(to_warehouse))

    # Get item details
    item_doc = frappe.get_cached_doc("Item", item_code)

    # Create Material Request
    material_request = frappe.new_doc("Material Request")
    material_request.transaction_date = nowdate()
    material_request.company = company
    material_request.material_request_type = "Material Transfer"

    # Add item row
    material_request.append("items", {
        "item_code": item_code,
        "item_name": item_doc.item_name,
        "description": item_doc.description,
        "qty": flt(qty),
        "uom": item_doc.stock_uom,
        "stock_uom": item_doc.stock_uom,
        "schedule_date": schedule_date or add_days(nowdate(), 7),
        "warehouse": to_warehouse,
        "from_warehouse": from_warehouse,
        "item_group": item_doc.item_group,
        "brand": item_doc.brand
    })

    # Set missing values and insert
    material_request.set_missing_values()
    material_request.insert(ignore_permissions=True)
    material_request.submit()

    return material_request.name


@frappe.whitelist()
def can_create_stock_transfer(source_warehouse):
    """Check if current user is from the source warehouse's branch (can fulfill the MR)."""
    if not source_warehouse:
        return True

    if frappe.session.user == "Administrator":
        return True

    roles = frappe.get_roles()
    if "System Manager" in roles or "Stock Manager" in roles:
        return True

    # Check if user's branch has this source warehouse
    user_branches = frappe.get_all(
        "Branch Configuration User",
        filters={"user": frappe.session.user},
        pluck="parent",
    )

    if not user_branches:
        return False

    branch_warehouses = frappe.get_all(
        "Branch Configuration Warehouse",
        filters={"parent": ["in", user_branches]},
        pluck="warehouse",
    )

    return source_warehouse in branch_warehouses


@frappe.whitelist()
def create_stock_transfer_from_mr(material_request):
    """Create a Stock Transfer from a submitted Material Request.
    Supports partial fulfillment — only includes pending qty per item.
    """
    mr = frappe.get_doc("Material Request", material_request)

    if mr.docstatus != 1:
        frappe.throw(_("Material Request must be submitted"))

    if mr.material_request_type != "Material Transfer":
        frappe.throw(_("Only Material Transfer type can create Stock Transfer"))

    source_wh = mr.set_from_warehouse
    target_wh = mr.set_warehouse

    if not source_wh and not target_wh:
        frappe.throw(_("Source or Target Warehouse is required on the Material Request"))

    # Calculate already transferred qty per MR item
    transferred_map = _get_transferred_qty_map(mr.name)

    st = frappe.new_doc("Stock Transfer")
    st.company = mr.company
    st.set_source_warehouse = source_wh or ""
    st.set_target_warehouse = target_wh or ""
    st.material_request_type = "Material Transfer"
    st.material_request = mr.name
    st.transaction_date = nowdate()

    has_pending = False
    for item in mr.items:
        already_transferred = flt(transferred_map.get(item.name, 0))
        pending_qty = flt(item.qty) - already_transferred

        if pending_qty <= 0:
            continue

        has_pending = True
        uom = item.uom or item.stock_uom
        conversion_factor = flt(item.conversion_factor) or 1

        st.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "quantity": pending_qty,
            "uom": uom,
            "stock_uom": item.stock_uom,
            "uom_conversion_factor": conversion_factor,
            "material_request_item": item.name,
            "mr_qty": flt(item.qty),
        })

        # Use item-level warehouses if header-level not set
        if not st.set_source_warehouse and item.from_warehouse:
            st.set_source_warehouse = item.from_warehouse
        if not st.set_target_warehouse and item.warehouse:
            st.set_target_warehouse = item.warehouse

    if not has_pending:
        frappe.throw(_("All items in this Material Request have already been fully transferred."))

    st.insert(ignore_permissions=True)

    # Link MR to Stock Transfer via comment
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Material Request",
        "reference_name": mr.name,
        "content": _("Stock Transfer {0} created").format(
            f'<a href="/app/stock-transfer/{st.name}">{st.name}</a>'
        ),
    }).insert(ignore_permissions=True)

    return st.name


def _get_transferred_qty_map(material_request):
    """Get total transferred qty per MR item from all active Stock Transfers.
    Excludes cancelled (docstatus=2) STs. Deleted STs are automatically
    excluded since their rows no longer exist in the database.
    Returns dict: {material_request_item_name: total_transferred_qty}
    """
    data = frappe.db.sql(
        """
        SELECT sti.material_request_item, SUM(sti.quantity) AS total_qty
        FROM `tabStock Transfer Item` sti
        INNER JOIN `tabStock Transfer` st ON st.name = sti.parent
        WHERE st.material_request = %s
        AND st.docstatus IN (0, 1)
        AND sti.material_request_item IS NOT NULL
        AND sti.material_request_item != ''
        GROUP BY sti.material_request_item
        """,
        (material_request,),
        as_dict=True,
    )
    return {row.material_request_item: flt(row.total_qty) for row in data}


@frappe.whitelist()
def get_mr_transfer_status(material_request):
    """Get transfer status for each item in a Material Request.
    Includes available qty from both source and target warehouses.
    """
    mr = frappe.get_doc("Material Request", material_request)
    transferred_map = _get_transferred_qty_map(material_request)

    source_wh = mr.set_from_warehouse
    target_wh = mr.set_warehouse

    result = []
    for item in mr.items:
        transferred = flt(transferred_map.get(item.name, 0))
        item_source_wh = item.from_warehouse or source_wh or ""
        item_target_wh = item.warehouse or target_wh or ""

        source_available = 0.0
        if item_source_wh:
            source_available = flt(
                frappe.db.get_value("Bin", {"item_code": item.item_code, "warehouse": item_source_wh}, "actual_qty")
            )

        target_available = 0.0
        if item_target_wh:
            target_available = flt(
                frappe.db.get_value("Bin", {"item_code": item.item_code, "warehouse": item_target_wh}, "actual_qty")
            )

        result.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "requested_qty": flt(item.qty),
            "transferred_qty": transferred,
            "pending_qty": flt(item.qty) - transferred,
            "source_available": source_available,
            "target_available": target_available,
            "source_warehouse": item_source_wh,
            "target_warehouse": item_target_wh,
        })

    return result