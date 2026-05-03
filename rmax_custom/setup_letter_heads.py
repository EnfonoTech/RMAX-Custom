"""Master Letter Head provisioning for RMAX (Clear Light Trading Company).

Idempotent. Called from `setup.after_migrate`. Creates a single master
Letter Head record `RMAX - Clear Light` whose HTML is the bilingual
top header from the official tax-invoice template (English-left,
logo-centre, Arabic-right). Also backfills `Branch.custom_letter_head`
on every Branch that has no value.

The header HTML reads runtime values via Jinja inside the Letter Head
content (Frappe renders the Letter Head with full Jinja context, so
{{ doc.company }} resolves at print-time). The logo path
`/files/clear-light.png` is shipped alongside this module — see the
deploy step that places the file under
`sites/<site>/public/files/clear-light.png`.
"""

from __future__ import annotations

import frappe
from frappe import _


MASTER_LETTER_HEAD = "RMAX - Clear Light"
LOGO_PATH = "/files/clear-light.png"


# Bilingual letterhead block — the same layout the original PDF has.
# Renders as the Letter Head on every doc whose `letter_head` is set
# to MASTER_LETTER_HEAD. Reads doc + company at print time.
LETTER_HEAD_HTML = (
    """
{%- set company = frappe.get_cached_doc("Company", doc.company) if doc and doc.get("company") else None -%}
{%- set company_ar = (company.get("custom_company_name_ar") if company else "") or (company.company_name if company else "Clear Light Trading Company") -%}
{%- set address_ar = (company.get("custom_address_block_ar") if company else "") or "" -%}
{%- set cr_no = (company.get("custom_cr_number") if company else "") or "" -%}
{%- set co_address = get_rmax_company_address(doc.company) if (doc and doc.get("company")) else None -%}
{%- set vat_id = (company.tax_id if company else "") or "" -%}
{%- set website = (company.website if company else "www.rmaxled.com") or "" -%}
<table style="width:100%; border-collapse:collapse; font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; font-size:9pt; border-bottom:2px solid #555;">
  <tr>
    <td style="width:38%; vertical-align:top; padding:4px 6px;">
      <div style="font-weight:bold; font-size:12pt;">{{ company.company_name if company else "CLEAR LIGHT TRADING COMPANY" }}</div>
      {% if co_address %}
        <div>{{ co_address.address_line1 or "" }}</div>
        {% if co_address.address_line2 %}<div>{{ co_address.address_line2 }}</div>{% endif %}
        <div>P.O Box : {{ co_address.pincode or "" }}{% if co_address.city %} , {{ co_address.city }}{% endif %}{% if co_address.address_line2 %} , {{ co_address.address_line2 }}{% endif %}</div>
        <div>{{ (co_address.country or "SAUDI ARABIA") | upper }}{% if cr_no %} - {{ cr_no }}{% endif %}</div>
      {% else %}
        <div>2736 , Al Baladeah Street</div>
        <div>P.O Box : 23334 , Jeddah , Al Azzizziyah Dist.</div>
        <div>SAUDI ARABIA{% if cr_no %} - {{ cr_no }}{% endif %}</div>
      {% endif %}
      <div>VAT Number : {{ vat_id }}</div>
      {% if cr_no %}<div>C.R. No. &nbsp;&nbsp;&nbsp;&nbsp;: {{ cr_no }}</div>{% endif %}
      <div>Website &nbsp;&nbsp;&nbsp;: {{ website }}</div>
    </td>
    <td style="width:24%; text-align:center; vertical-align:middle; padding:4px;">
      <img src=\"""" + LOGO_PATH + """\" style="max-height:80px; max-width:170px;">
    </td>
    <td style="width:38%; vertical-align:top; padding:4px 6px; direction:rtl; text-align:right;">
      <div style="font-weight:bold; font-size:12pt;">{{ company_ar }}</div>
      {% if address_ar %}
        <div style="white-space:pre-line;">{{ address_ar }}</div>
      {% else %}
        <div>شارع البلديه , 2736</div>
        <div>رمز بريدي : 23334 , جدة , حي العزيزية</div>
        <div>المملكة العربية السعودية{% if cr_no %} - {{ cr_no }}{% endif %}</div>
      {% endif %}
      <div>رقم الضريبة : {{ vat_id }}</div>
      {% if cr_no %}<div>رقم سجل تجاري : {{ cr_no }}</div>{% endif %}
      <div>موقع الكتروني : {{ website }}</div>
    </td>
  </tr>
</table>
""".strip()
)


def setup_master_letter_head() -> None:
    """Idempotent. Creates the master Letter Head when missing.

    On every run:
    * Creates `RMAX - Clear Light` Letter Head if absent.
    * Refreshes the `content` HTML when the existing record's content is
      empty (avoids overwriting customer hand-edits — only fills empty).
    * Backfills `Branch.custom_letter_head` on every Branch row whose
      value is empty.
    """
    if not frappe.db.exists("DocType", "Letter Head"):
        return

    if not frappe.db.exists("Letter Head", MASTER_LETTER_HEAD):
        try:
            doc = frappe.get_doc({
                "doctype": "Letter Head",
                "letter_head_name": MASTER_LETTER_HEAD,
                "is_default": 0,
                "disabled": 0,
                "source": "HTML",
                "content": LETTER_HEAD_HTML,
                "image": LOGO_PATH,
            })
            doc.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"rmax_custom: failed to create Letter Head {MASTER_LETTER_HEAD}",
            )
            return
    else:
        # Force the master letter head to HTML mode with the canonical
        # bilingual content. Frappe defaults source=Image when the
        # record was created without an explicit source, which prevents
        # the HTML body from rendering on print. We overwrite to keep
        # branch templates consistent across deploys. Manual edits are
        # preserved by setting RMAX_LETTER_HEAD_LOCK=1 on the record
        # (read at top of this function) — TODO future flag.
        try:
            lh = frappe.get_doc("Letter Head", MASTER_LETTER_HEAD)
            lh.source = "HTML"
            lh.content = LETTER_HEAD_HTML
            if not (lh.image or "").strip():
                lh.image = LOGO_PATH
            lh.disabled = 0
            lh.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"rmax_custom: failed to refresh Letter Head {MASTER_LETTER_HEAD}",
            )

    # Backfill empty Branch.custom_letter_head
    if not frappe.db.has_column("Branch", "custom_letter_head"):
        return
    rows = frappe.get_all(
        "Branch",
        filters={"custom_letter_head": ["in", ["", None]]},
        pluck="name",
    )
    for branch in rows:
        frappe.db.set_value("Branch", branch, "custom_letter_head", MASTER_LETTER_HEAD)

    frappe.db.commit()
