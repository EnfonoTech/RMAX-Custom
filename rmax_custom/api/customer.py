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
	vat = cstr(doc.get("custom_vat_registration_number")).strip()
	if not vat:
		return

	if doc.get("customer_type") == "Branch":
		return

	if count_digits(vat) != 15:
		frappe.throw(_("VAT Registration Number must be exactly 15 digits."))

	# Persist the trimmed value so DB always stores the clean form
	if doc.get("custom_vat_registration_number") != vat:
		doc.custom_vat_registration_number = vat

	if doc.get("custom_allow_duplicate_vat"):
		if not _can_override_vat_duplicate():
			frappe.throw(
				_("You do not have permission to override the VAT duplicate check. Required role: Sales Manager.")
			)
		if not cstr(doc.get("custom_duplicate_vat_reason")).strip():
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
			_(
				"VAT Registration Number already used by Customer: {0}. "
				"A Sales Manager can tick 'Allow Duplicate VAT' to override."
			).format(clash[0].name)
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
):
    """Create a Customer plus its primary billing/shipping Address atomically.

    All input strings are trimmed. VAT, mobile and pincode are validated
    server-side mirroring the client dialog so direct API callers get the
    same guardrails. If Address creation fails for any reason after the
    Customer has been inserted, the Customer is rolled back so callers
    never end up with an orphan record.
    """

    customer_name = cstr(customer_name).strip()
    mobile_no = cstr(mobile_no).strip()
    email_id = cstr(email_id).strip() or None
    customer_type = cstr(customer_type).strip() or "Company"
    custom_vat_registration_number = cstr(custom_vat_registration_number).strip() or None
    duplicate_vat_reason = cstr(duplicate_vat_reason).strip() or None
    address_type = cstr(address_type).strip() or None
    address_line1 = cstr(address_line1).strip() or None
    address_line2 = cstr(address_line2).strip() or None
    custom_building_number = cstr(custom_building_number).strip() or None
    custom_area = cstr(custom_area).strip() or None
    city = cstr(city).strip() or None
    state = cstr(state).strip() or None
    pincode = cstr(pincode).strip() or None

    if not customer_name:
        frappe.throw(_("Customer Name is required"))

    if not mobile_no:
        frappe.throw(_("Mobile No is required"))

    if count_digits(mobile_no) < 10:
        frappe.throw(_("Mobile number must have at least 10 digits."))

    if pincode and count_digits(pincode) != 5:
        frappe.throw(_("Postal Code must be exactly 5 digits."))

    allow_duplicate_vat = int(allow_duplicate_vat or 0)

    # VAT duplicate handling
    if custom_vat_registration_number and customer_type != "Branch":
        if count_digits(custom_vat_registration_number) != 15:
            frappe.throw(_("VAT Registration Number must be exactly 15 digits."))

        if allow_duplicate_vat:
            if not _can_override_vat_duplicate():
                frappe.throw(
                    _("You do not have permission to override the VAT duplicate check. Required role: Sales Manager.")
                )
            if not duplicate_vat_reason:
                frappe.throw(_("Duplicate VAT Reason is required when overriding the VAT duplicate check."))
        else:
            clash = frappe.db.get_value(
                "Customer",
                {"custom_vat_registration_number": custom_vat_registration_number},
                "name",
            )
            if clash:
                frappe.throw(
                    _(
                        "VAT Registration Number already used by Customer: {0}. "
                        "A Sales Manager can tick 'Allow Duplicate VAT' on the Customer to override."
                    ).format(clash)
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
        "customer_type": customer_type,
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
    customer.insert(ignore_permissions=True)

    try:
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
            "email_id": email_id,
            "phone": mobile_no,
            "is_primary_address": 1,
            "is_shipping_address": 1,
        })
        address.append("links", {
            "link_doctype": "Customer",
            "link_name": customer.name,
            "link_title": customer.customer_name,
        })
        address.insert(ignore_permissions=True)

        customer.customer_primary_address = address.name
        customer.save(ignore_permissions=True)
    except Exception:
        # Roll the Customer back so we don't leave an orphan when the
        # address fails for any reason (validation, network, etc.).
        frappe.db.rollback()
        raise

    return {
        "customer": customer.name,
        "address": address.name,
        "message": _("Customer {0} and Address created successfully").format(customer.name),
    }



@frappe.whitelist()
def validate_vat_customer(vat, customer_type, name=None, allow_duplicate_vat=0):
    """Live VAT duplicate check called from Customer form + Create Customer dialog."""
    vat = cstr(vat).strip()
    if not vat:
        return
    if customer_type == "Branch":
        return

    if count_digits(vat) != 15:
        frappe.throw(_("VAT Registration Number must be exactly 15 digits."))

    if int(allow_duplicate_vat or 0):
        if not _can_override_vat_duplicate():
            frappe.throw(
                _("You do not have permission to override the VAT duplicate check. Required role: Sales Manager.")
            )
        return

    existing = frappe.get_all(
        "Customer",
        filters={
            "custom_vat_registration_number": vat,
            "name": ["!=", cstr(name) or ""],
        },
        fields=["name"],
        limit=1,
    )

    if existing:
        frappe.throw(
            _(
                "VAT Registration Number already used by Customer: {0}. "
                "A Sales Manager can tick 'Allow Duplicate VAT' on the Customer to override."
            ).format(existing[0].name)
        )



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