"""
Jinja helpers for RMAX print formats.

Registered via `jinja.methods` in hooks.py — accessible as
`get_rmax_zatca_qr(doc)` and `get_rmax_company_bank_accounts(company)` from
within Print Format Jinja templates.

These helpers wrap optional dependencies (ksa_compliance) so the templates
render gracefully on sites where Phase 2 settings are missing.
"""

from __future__ import annotations

import frappe


def get_rmax_zatca_qr(doc) -> str | None:
    """
    Return a base64 data-URI for the ZATCA QR (Phase 2 if available, Phase 1
    fallback). Returns None when neither helper is available or both fail.

    Safe to call on any doctype — returns None for non-Sales-Invoice docs.
    """
    if not doc or getattr(doc, "doctype", None) != "Sales Invoice":
        return None

    name = doc.name
    if not name:
        return None

    try:
        from ksa_compliance.jinja import (
            get_phase_2_print_format_details,
            get_zatca_phase_1_qr_for_invoice,
        )
    except ImportError:
        return None

    try:
        details = get_phase_2_print_format_details(doc)
        if details and getattr(details, "siaf", None):
            qr = getattr(details.siaf, "qr_image_src", None)
            if qr:
                return qr
    except Exception:
        # Phase 2 not configured — fall through to Phase 1.
        pass

    try:
        return get_zatca_phase_1_qr_for_invoice(name)
    except Exception:
        return None


def get_rmax_company_bank_accounts(company: str) -> list[dict]:
    """
    Return company bank accounts for the print footer.

    Order: default account first, then by name. Disabled rows excluded.
    """
    if not company:
        return []

    return frappe.get_all(
        "Bank Account",
        filters={"is_company_account": 1, "company": company, "disabled": 0},
        fields=["bank", "bank_account_no", "iban", "is_default"],
        order_by="is_default desc, name asc",
    )


def get_rmax_company_address(company: str) -> dict | None:
    """
    Return the primary linked Address for a Company as a dict (or None).
    """
    if not company:
        return None

    link = frappe.db.get_value(
        "Dynamic Link",
        {"link_doctype": "Company", "link_name": company, "parenttype": "Address"},
        ["parent"],
    )
    if not link:
        return None

    return frappe.db.get_value(
        "Address",
        link,
        ["address_line1", "address_line2", "city", "pincode", "country"],
        as_dict=True,
    )


def get_rmax_customer_phone(doc) -> str:
    """
    Resolve customer phone for the print buyer block.

    Priority: contact_mobile on doc → linked Contact mobile → Customer mobile_no.
    """
    if not doc:
        return ""

    if getattr(doc, "contact_mobile", None):
        return doc.contact_mobile

    if getattr(doc, "contact_person", None):
        mobile = frappe.db.get_value("Contact", doc.contact_person, "mobile_no")
        if mobile:
            return mobile

    customer = getattr(doc, "customer", None)
    if customer:
        return frappe.db.get_value("Customer", customer, "mobile_no") or ""

    return ""
