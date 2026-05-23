import frappe
from frappe import _
from frappe.utils import cint


VAT_DUPLICATE_OVERRIDE_ROLES = {
    "Purchase Manager",
    "Purchase Master Manager",
    "System Manager",
}


def _can_override_vat_duplicate(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return bool(set(frappe.get_roles(user)) & VAT_DUPLICATE_OVERRIDE_ROLES)


def enforce_vat_duplicate_rule(doc, method=None):
    """Supplier.validate hook — server-side tax_id duplicate enforcement."""
    tax_id = (doc.get("tax_id") or "").strip()
    if not tax_id:
        return

    if len(tax_id) != 15:
        frappe.throw(_("VAT Registration Number must be exactly 15 digits."))

    if doc.get("custom_allow_duplicate_vat"):
        if not _can_override_vat_duplicate():
            frappe.throw(
                _("You do not have permission to override the VAT duplicate check. Required role: Purchase Manager.")
            )
        if not (doc.get("custom_duplicate_vat_reason") or "").strip():
            frappe.throw(_("Duplicate VAT Reason is required when 'Allow Duplicate VAT' is ticked."))
        return

    clash = frappe.get_all(
        "Supplier",
        filters={
            "tax_id": tax_id,
            "name": ["!=", doc.name or ""],
        },
        fields=["name"],
        limit=1,
    )
    if clash:
        frappe.throw(
            _("VAT Registration Number already used by Supplier: {0}. A Purchase Manager can tick 'Allow Duplicate VAT' to override.").format(clash[0].name)
        )


def _get_default_supplier_group():
    sg = frappe.db.get_single_value("Buying Settings", "supplier_group")
    if sg and not cint(frappe.db.get_value("Supplier Group", sg, "is_group")):
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
    supplier_type="Company",
    email_id=None,
    country=None,
    tax_id=None,
    address_type=None,
    address_line1=None,
    address_line2=None,
    custom_building_number=None,
    city=None,
    pincode=None,
    custom_area=None,
    allow_duplicate_vat=0,
    duplicate_vat_reason=None,
    buyer_kind=None,
):
    if not supplier_name:
        frappe.throw(_("Supplier Name is required"))

    allow_duplicate_vat = int(allow_duplicate_vat or 0)

    if tax_id:
        tax_id = tax_id.strip()
        if len(tax_id) != 15:
            frappe.throw(_("VAT Registration Number must be exactly 15 digits."))

        if allow_duplicate_vat:
            if not _can_override_vat_duplicate():
                frappe.throw(
                    _("You do not have permission to override the VAT duplicate check. Required role: Purchase Manager.")
                )
            if not (duplicate_vat_reason and duplicate_vat_reason.strip()):
                frappe.throw(_("Duplicate VAT Reason is required when overriding the VAT duplicate check."))
        else:
            clash = frappe.db.exists("Supplier", {"tax_id": tax_id})
            if clash:
                frappe.throw(
                    _("VAT Registration Number already used by Supplier: {0}. A Purchase Manager can tick 'Allow Duplicate VAT' on the Supplier to override.").format(clash)
                )

    if frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
        frappe.throw(_("Supplier '{0}' already exists").format(supplier_name))

    if not country:
        company = frappe.defaults.get_user_default("company")
        if company:
            country = frappe.db.get_value("Company", company, "country")

    supplier = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": supplier_name,
        "supplier_type": supplier_type or "Company",
        "supplier_group": _get_default_supplier_group(),
        "country": country,
        "mobile_no": mobile_no or None,
        "email_id": email_id or None,
        "tax_id": tax_id or None,
        "custom_allow_duplicate_vat": 1 if allow_duplicate_vat else 0,
        "custom_duplicate_vat_reason": duplicate_vat_reason if allow_duplicate_vat else None,
    })
    supplier.insert(ignore_permissions=True)

    address_name = None
    has_address_payload = any([
        address_line1, address_line2, city, custom_area, custom_building_number, pincode,
    ])
    if has_address_payload:
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": supplier_name,
            "address_type": address_type or "Billing",
            "address_line1": address_line1,
            "address_line2": address_line2,
            "city": city,
            "custom_area": custom_area,
            "custom_building_number": custom_building_number,
            "pincode": pincode,
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
