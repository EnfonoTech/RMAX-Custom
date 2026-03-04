import frappe
from frappe import _
from frappe.utils import nowdate, add_days, flt





@frappe.whitelist()
def create_customer_with_primary_address(
    customer_name,
    mobile_no=None,
    email_id=None,
    address_type=None,
    address_line1=None,
    address_line2=None,
    city=None,
    country=None,
    default_currency=None
):

    if not customer_name:
        frappe.throw("Customer Name is required")

    if not mobile_no:
        frappe.throw("Mobile No is required")

    if not address_line1 or not city or not country:
        frappe.throw("Address details are required")
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": customer_name,
        "customer_type": "Individual",
        "customer_group": "All Customer Groups",
        "territory": "All Territories",
        "mobile_no": mobile_no,
        "email_id": email_id,
        "default_currency": default_currency
    })

    customer.insert(ignore_permissions=True)
    address = frappe.get_doc({
        "doctype": "Address",
        "address_title": customer_name,
        "address_type": address_type,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "country": country
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


