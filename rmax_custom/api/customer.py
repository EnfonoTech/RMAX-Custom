import frappe
from frappe import _
from frappe.utils import cstr
from frappe.core.doctype.user_permission.user_permission import get_permitted_documents
import re


# Roles allowed to override the VAT duplicate check on Customer
VAT_DUPLICATE_OVERRIDE_ROLES = {
	"Sales Manager",
	"Sales Master Manager",
	"System Manager",
}


def _can_override_vat_duplicate(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)) & VAT_DUPLICATE_OVERRIDE_ROLES)


def enforce_vat_duplicate_rule(doc, method=None):
	"""Customer.validate hook. Server-side enforcement of VAT duplicate rule.

	Ensures override flag is only honoured for permitted roles and that
	direct API writes cannot silently bypass the duplicate check.
	"""
	vat = (doc.get("custom_vat_registration_number") or "").strip()
	if not vat:
		return

	if doc.get("customer_type") == "Branch":
		return

	if len(vat) != 15:
		frappe.throw(_("VAT Registration Number must be exactly 15 digits."))

	if doc.get("custom_allow_duplicate_vat"):
		if not _can_override_vat_duplicate():
			frappe.throw(
				_("You do not have permission to override the VAT duplicate check. Required role: Sales Manager.")
			)
		if not (doc.get("custom_duplicate_vat_reason") or "").strip():
			frappe.throw(_("Duplicate VAT Reason is required when 'Allow Duplicate VAT' is ticked."))
		return

	clash = frappe.get_all(
		"Customer",
		filters={
			"custom_vat_registration_number": vat,
			"name": ["!=", doc.name or ""],
		},
		fields=["name"],
		limit=1,
	)
	if clash:
		frappe.throw(
			_("VAT Registration Number already used by Customer: {0}. A Sales Manager can tick 'Allow Duplicate VAT' to override.").format(clash[0].name)
		)



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
    customer_type="Company",
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
    allow_duplicate_vat=0,
    duplicate_vat_reason=None,
    buyer_kind=None,
    custom_customer_name_ar: str = "",
):

    if not customer_name:
        frappe.throw(_("Customer Name is required"))

    if not mobile_no:
        frappe.throw(_("Mobile No is required"))

    if count_digits(mobile_no) < 10:
        frappe.throw("Mobile number must have at least 10 digits.")

    allow_duplicate_vat = int(allow_duplicate_vat or 0)

    # B2B / B2C gating — mirrors the dialog rules so direct API callers
    # cannot save a B2B customer without VAT + Address.
    is_b2b = (buyer_kind or "").startswith("B2B") or (
        not buyer_kind and customer_type == "Company"
    )

    if is_b2b:
        if not custom_vat_registration_number:
            frappe.throw(_("VAT Registration Number is required for B2B (Company) customers."))
        for label, value in (
            (_("Address Line 1"), address_line1),
            (_("Building Number"), custom_building_number),
            (_("Area/District"), custom_area),
            (_("City/Town"), city),
            (_("Postal Code"), pincode),
        ):
            if not value:
                frappe.throw(_("{0} is required for B2B (Company) customers.").format(label))
        if pincode and len(str(pincode)) != 5:
            frappe.throw(_("Postal Code must be exactly 5 digits."))

    # VAT duplicate handling
    if custom_vat_registration_number and customer_type != "Branch":
        if len(str(custom_vat_registration_number)) != 15:
            frappe.throw(_("VAT Registration Number must be exactly 15 digits."))

        if allow_duplicate_vat:
            if not _can_override_vat_duplicate():
                frappe.throw(
                    _("You do not have permission to override the VAT duplicate check. Required role: Sales Manager.")
                )
            if not (duplicate_vat_reason and duplicate_vat_reason.strip()):
                frappe.throw(_("Duplicate VAT Reason is required when overriding the VAT duplicate check."))
        else:
            clash = frappe.db.exists(
                "Customer",
                {"custom_vat_registration_number": custom_vat_registration_number},
            )
            if clash:
                frappe.throw(
                    _("VAT Registration Number already used by Customer: {0}. A Sales Manager can tick 'Allow Duplicate VAT' on the Customer to override.").format(clash)
                )

    # Prevent duplicate by name
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
        "customer_type": customer_type or "Company",
        "customer_group": _get_default_customer_group(),
        "territory": _get_default_territory(),
        "default_currency": default_currency,
        "tax_id": tax_id,
        "mobile_no": mobile_no,
        "email_id": email_id,
        "custom_vat_registration_number": custom_vat_registration_number,
        "custom_allow_duplicate_vat": 1 if allow_duplicate_vat else 0,
        "custom_duplicate_vat_reason": duplicate_vat_reason if allow_duplicate_vat else None,
    })

    if custom_customer_name_ar:
        customer.custom_customer_name_ar = custom_customer_name_ar

    customer.insert(ignore_permissions=True)

    # Address only when there's actually something to store. B2C path
    # leaves every address field blank — skip the Address insert
    # entirely so we don't trip Address.validate's mandatory checks.
    address_name = None
    has_address_payload = any([
        address_line1, address_line2, city, custom_area, custom_building_number, pincode,
    ])
    if has_address_payload:
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
            "is_shipping_address": 1,
        })
        address.append("links", {
            "link_doctype": "Customer",
            "link_name": customer.name,
            "link_title": customer.customer_name,
        })
        address.insert(ignore_permissions=True)
        address_name = address.name

        customer.customer_primary_address = address_name
        customer.save(ignore_permissions=True)

    return {
        "customer": customer.name,
        "address": address_name,
        "message": _("Customer {0} created successfully").format(customer.name),
    }



@frappe.whitelist()
def validate_vat_customer(vat, customer_type, name=None, allow_duplicate_vat=0):
    if not vat:
        return
    if customer_type == "Branch":
        return

    allow_duplicate_vat = int(allow_duplicate_vat or 0)

    if allow_duplicate_vat:
        if not _can_override_vat_duplicate():
            frappe.throw(
                _("You do not have permission to override the VAT duplicate check. Required role: Sales Manager.")
            )
        return

    existing = frappe.get_all(
        "Customer",
        filters={
            "custom_vat_registration_number": vat,
            "name": ["!=", name]
        },
        fields=["name"]
    )

    if existing:
        frappe.throw(
            _("VAT Registration Number already used by Customer: {0}. A Sales Manager can tick 'Allow Duplicate VAT' on the Customer to override.").format(existing[0].name)
        )

    return



def count_digits(value):
    if not value:
        return 0
    return len(re.sub(r"\D", "", value))


@frappe.whitelist()
def validate_phone_numbers(mobile_no=None, phone_no=None):
    if mobile_no:
        if count_digits(mobile_no) < 10:
            frappe.throw("Mobile number must have at least 10 digits.")
    if phone_no:
        if count_digits(phone_no) < 10:
            frappe.throw("Phone number must have at least 10 digits.")