import frappe
from frappe import _
from frappe.utils import cstr
from frappe.core.doctype.user_permission.user_permission import get_permitted_documents


def _get_default_customer_group():
	permitted = get_permitted_documents("Customer Group")
	return (permitted[0] if permitted else None) or frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups"


def _get_default_territory():
	permitted = get_permitted_documents("Territory")
	return (permitted[0] if permitted else None) or frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"


@frappe.whitelist()
def create_customer_with_address(
    customer_name,
    mobile_no=None,
    customer_type="Individual",
    email_id=None,
    country=None,
    default_currency=None,
    tax_id=None,
    custom_vat_registration_number=None,
    commercial_registration_number=None,
    address_type=None,
    address_line1=None,
    address_line2=None,
    custom_building_number=None,
    city=None,
    state=None,
    pincode=None,
    custom_area=None,


):

    if not customer_name:
        frappe.throw(_("Customer Name is required"))

    if not mobile_no:
        frappe.throw(_("Mobile No is required"))

    # Prevent duplicate
    if frappe.db.exists("Customer", {"customer_name": customer_name}):
        frappe.throw(_("Customer already exists"))

    # Get company defaults
    if not country or not default_currency:
        permitted_companies = get_permitted_documents("Company")
        company = (permitted_companies[0] if permitted_companies else None) \
            or frappe.defaults.get_user_default("company")

        if not company:
            frappe.throw(_("Please set a default company"))

        company_doc = frappe.get_cached_doc("Company", company)

        country = country or company_doc.country
        default_currency = default_currency or company_doc.default_currency

    # Create Customer
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": customer_name,
        "customer_type": customer_type or "Individual",
        "customer_group": _get_default_customer_group(),
        "territory": _get_default_territory(),
        "default_currency": default_currency,
        "tax_id": tax_id,
        "mobile_no": mobile_no,
        "email_id": email_id,
        "custom_vat_registration_number": custom_vat_registration_number,
    })

    customer.insert(ignore_permissions=True)

    address_name = None

    address = frappe.get_doc({
        "doctype": "Address",
        "address_title": customer_name,
        "address_type": address_type or "Billing",
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "state": state,
        "custom_area": custom_area,
        "custom_building_number": custom_building_number,
        "pincode": pincode,
        "country": country,
        "is_primary_address": 1,
        "is_shipping_address": 1
    })
    address.append("links", {
        "link_doctype": "Customer",
        "link_name": customer.name,
        "link_title": customer.customer_name
    })

    address.insert(ignore_permissions=True)
    customer.customer_primary_address = address.name
    customer.save(ignore_permissions=True)

    return {
        "customer": customer.name,
        "address": address.name,
        "message": "Customer and Address created successfully"
    }

