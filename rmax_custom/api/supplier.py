import frappe
from frappe import _


def _get_default_supplier_group():
    sg = frappe.db.get_single_value("Buying Settings", "supplier_group")
    if sg and not frappe.db.get_value("Supplier Group", sg, "is_group"):
        return sg
    leaf = frappe.get_all(
        "Supplier Group",
        filters={"is_group": 0},
        fields=["name"],
        limit=1,
        order_by="name asc",
    )
    return (leaf[0].name if leaf else None) or sg or "All Supplier Groups"


@frappe.whitelist()
def create_supplier_with_address(
    supplier_name,
    mobile_no=None,
    email_id=None,
    tax_id=None,
    country=None,
    address_type=None,
    address_line1=None,
    address_line2=None,
    custom_building_number=None,
    custom_area=None,
    city=None,
    pincode=None,
):
    if not supplier_name:
        frappe.throw(_("Supplier Name is required"))

    if frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
        frappe.throw(_("Supplier '{0}' already exists").format(supplier_name))

    if not country:
        company = frappe.defaults.get_user_default("company")
        if company:
            country = frappe.db.get_value("Company", company, "country")

    supplier = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": supplier_name,
        "supplier_group": _get_default_supplier_group(),
        "country": country,
        "mobile_no": mobile_no or None,
        "email_id": email_id or None,
        "tax_id": tax_id or None,
    })
    supplier.insert(ignore_permissions=True)

    address_name = None
    has_address = any([address_line1, city, custom_area, custom_building_number, pincode])
    if has_address:
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": supplier_name,
            "address_type": address_type or "Billing",
            "address_line1": address_line1,
            "address_line2": address_line2 or None,
            "city": city,
            "custom_area": custom_area or None,
            "custom_building_number": custom_building_number or None,
            "pincode": pincode or None,
            "country": country,
            "is_primary_address": 1,
            "is_shipping_address": 1,
        })
        address.append("links", {
            "link_doctype": "Supplier",
            "link_name": supplier.name,
            "link_title": supplier.supplier_name,
        })
        address.insert(ignore_permissions=True)
        address_name = address.name

        supplier.supplier_primary_address = address_name
        supplier.save(ignore_permissions=True)

    return {
        "supplier": supplier.name,
        "address": address_name,
        "message": _("Supplier {0} created successfully").format(supplier.name),
    }
