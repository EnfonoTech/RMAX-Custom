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


def get_rmax_hijri_date(d) -> str:
    """
    Convert a Gregorian `datetime.date` (or YYYY-MM-DD string) to Hijri
    `dd/mm/yyyy` for bilingual print headers.

    Falls back to empty string when conversion library missing.  No raise.
    """
    if not d:
        return ""
    try:
        # `hijri_converter` is shipped by ksa_compliance's deps.
        from hijri_converter import Gregorian
    except ImportError:
        try:
            from hijri_converter.convert import Gregorian  # type: ignore
        except Exception:
            return ""

    try:
        if isinstance(d, str):
            from datetime import date as _date
            parts = d.split("-")
            if len(parts) != 3:
                return ""
            d = _date(int(parts[0]), int(parts[1]), int(parts[2]))
        h = Gregorian(d.year, d.month, d.day).to_hijri()
        return f"{h.day:02d}/{h.month:02d}/{h.year:04d}"
    except Exception:
        return ""


def get_rmax_letter_head_html(doc) -> str:
    """
    Resolve the Letter Head HTML for a printed doc.

    Priority:
      1. doc.letter_head if set + enabled + has content
      2. `RMAX - <Branch>` if doc.branch resolves
      3. `RMAX - Clear Light` master fallback
      4. Empty string

    Embedded inline in the print format so the wrapper-letterhead toggle in
    the print dialog can't accidentally strip the header (operators kept
    leaving it on "No Letter Head").
    """
    candidates: list[str] = []

    lh = getattr(doc, "letter_head", None)
    if lh:
        candidates.append(lh)

    branch = getattr(doc, "branch", None) if doc else None
    if branch:
        candidates.append(f"RMAX - {branch}")

    candidates.append("RMAX - Clear Light")

    for name in candidates:
        if not name:
            continue
        row = frappe.db.get_value(
            "Letter Head",
            {"name": name, "disabled": 0},
            ["content", "source"],
            as_dict=True,
        )
        content = (row or {}).get("content") or ""
        if not content.strip():
            continue
        # Letter Head bodies are Jinja templates — render with the doc in context
        # so {{ doc.* }} and helper calls inside the letter head resolve.
        try:
            return frappe.render_template(content, {"doc": doc, "company": getattr(doc, "company", None)})
        except Exception:
            return content

    return ""


def get_rmax_invoice_title(doc):
    """Jinja-facing alias for :func:`get_invoice_title`.

    Registered in ``hooks.py`` as ``get_rmax_invoice_title`` so print format
    templates call ``get_rmax_invoice_title(doc)`` consistently with other
    ``get_rmax_*`` helpers.
    """
    return get_invoice_title(doc)


def get_invoice_title(doc):
    """Return ``(en_title, ar_title)`` for a Sales Invoice / Delivery Note doc.

    Resolves to the simplified pair when:
    - ``Customer.custom_is_b2c`` is truthy, OR
    - ``Customer.tax_id`` is empty/whitespace.

    Both signals indicate a B2C transaction per ZATCA Phase-2 conventions and
    the client docx (Section A.5).
    """
    customer_name = doc.get("customer") if hasattr(doc, "get") else getattr(doc, "customer", None)
    if not customer_name:
        return ("Tax Invoice", "فاتورة ضريبية")

    customer = frappe.get_cached_doc("Customer", customer_name)
    is_b2c = bool(customer.get("custom_is_b2c"))
    has_vat = bool((customer.get("tax_id") or "").strip())

    if is_b2c or not has_vat:
        return ("Simplified Tax Invoice", "فاتورة ضريبية مبسطة")
    return ("Tax Invoice", "فاتورة ضريبية")


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
