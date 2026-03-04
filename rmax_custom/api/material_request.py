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