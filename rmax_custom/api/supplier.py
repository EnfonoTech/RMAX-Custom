import re

import frappe
from frappe import _
from frappe.utils import cint
from frappe.core.doctype.user_permission.user_permission import get_permitted_documents


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


def _count_digits(value):
    if not value:
        return 0
    return len(re.sub(r"\D", "", str(value)))


def enforce_vat_duplicate_rule(doc, method=None):
    """Supplier.validate hook — server-side tax_id duplicate enforcement."""
    # Branch suppliers are exempt from VAT validation
    if doc.get("supplier_type") == "Branch":
        return

    tax_id = (doc.get("tax_id") or "").strip()

    # Company type requires a Tax ID
    if doc.get("supplier_type") == "Company" and not tax_id:
        frappe.throw(_("VAT Registration Number is required for Company type suppliers."))

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
    """Priority:
    1. User Permission for Supplier Group — default one first, then first permitted.
    2. Buying Settings default — only if it is a leaf (is_group = 0).
    3. First non-group Supplier Group found in the system (alphabetical).
    """
    # 1. User Permissions for Supplier Group
    permitted = frappe.get_all(
        "User Permission",
        filters={"user": frappe.session.user, "allow": "Supplier Group"},
        fields=["for_value", "is_default"],
        order_by="is_default desc",
    )
    if permitted:
        default = next((p.for_value for p in permitted if p.is_default), None)
        return default or permitted[0].for_value

    # 2. Buying Settings default
    sg = frappe.db.get_single_value("Buying Settings", "supplier_group")
    if sg and not cint(frappe.db.get_value("Supplier Group", sg, "is_group")):
        return sg

    # 3. First non-group Supplier Group alphabetically
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
    supplier_group=None,
):
    if not supplier_name:
        frappe.throw(_("Supplier Name is required"))

    is_branch = supplier_type == "Branch"
    is_b2b = (buyer_kind or "").startswith("B2B") or (
        not buyer_kind and supplier_type == "Company"
    )

    # Mobile required for non-Branch
    if not is_branch:
        if not mobile_no:
            frappe.throw(_("Mobile No is required"))
        if _count_digits(mobile_no) < 10:
            frappe.throw(_("Mobile number must have at least 10 digits."))

    allow_duplicate_vat = int(allow_duplicate_vat or 0)

    # B2B gating — VAT + full address mandatory
    if is_b2b:
        if not tax_id:
            frappe.throw(_("VAT Registration Number is required for B2B (Company) suppliers."))
        for label, value in (
            (_("Address Line 1"), address_line1),
            (_("Building Number"), custom_building_number),
            (_("Area/District"), custom_area),
            (_("City/Town"), city),
            (_("Postal Code"), pincode),
        ):
            if not value:
                frappe.throw(_("{0} is required for B2B (Company) suppliers.").format(label))
        if pincode and len(str(pincode)) != 5:
            frappe.throw(_("Postal Code must be exactly 5 digits."))

    # VAT validation — Branch is exempt
    if tax_id and not is_branch:
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

    # Prevent duplicate by name
    if frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
        frappe.throw(_("Supplier '{0}' already exists").format(supplier_name))

    if not country:
        permitted_companies = get_permitted_documents("Company")
        company = (permitted_companies[0] if permitted_companies else None) \
            or frappe.defaults.get_user_default("company")
        if company:
            country = frappe.db.get_value("Company", company, "country")

    supplier = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": supplier_name,
        "supplier_type": supplier_type or "Company",
        "supplier_group": supplier_group or _get_default_supplier_group(),
        "country": country,
        "mobile_no": mobile_no or None,
        "email_id": email_id or None,
        "tax_id": (tax_id if not is_branch else None) or None,
        "custom_allow_duplicate_vat": 1 if allow_duplicate_vat else 0,
        "custom_duplicate_vat_reason": duplicate_vat_reason if allow_duplicate_vat else None,
    })
    supplier.insert(ignore_permissions=True)

    address_name = None
    if address_line1:
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


@frappe.whitelist()
def validate_vat_supplier(tax_id, supplier_type, name=None, allow_duplicate_vat=0):
    if not tax_id:
        return
    if supplier_type == "Branch":
        return

    allow_duplicate_vat = int(allow_duplicate_vat or 0)

    if allow_duplicate_vat:
        if not _can_override_vat_duplicate():
            frappe.throw(
                _("You do not have permission to override the VAT duplicate check. Required role: Purchase Manager.")
            )
        return

    existing = frappe.get_all(
        "Supplier",
        filters={
            "tax_id": tax_id,
            "name": ["!=", name]
        },
        fields=["name"]
    )

    if existing:
        frappe.throw(
            _("VAT Registration Number already used by Supplier: {0}. A Purchase Manager can tick 'Allow Duplicate VAT' on the Supplier to override.").format(existing[0].name)
        )
