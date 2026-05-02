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
{%- set company = frappe.get_cached_doc("Company", doc.company) -%}
{%- set company_ar = company.get("custom_company_name_ar") or company.company_name -%}
{%- set address_ar = company.get("custom_address_block_ar") or "" -%}
{%- set cr_no = company.get("custom_cr_number") or "" -%}
{%- set co_address = frappe.call("rmax_custom.print_helpers.get_rmax_company_address", company=doc.company) -%}
<table style="width:100%; border-collapse:collapse; font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; font-size:9pt;">
  <tr>
    <td style="width:40%; vertical-align:top; padding:4px 6px;">
      <div style="font-weight:bold; font-size:11pt;">{{ company.company_name }}</div>
      {% if co_address %}
        <div>{{ co_address.address_line1 or "" }}</div>
        {% if co_address.address_line2 %}<div>{{ co_address.address_line2 }}</div>{% endif %}
        <div>
          {{ co_address.city or "" }}{% if co_address.pincode %} - {{ co_address.pincode }}{% endif %}{% if co_address.country %}, {{ co_address.country }}{% endif %}
        </div>
      {% endif %}
      <div>VAT Number : {{ company.tax_id or "" }}</div>
      {% if cr_no %}<div>C.R. No. &nbsp;: {{ cr_no }}</div>{% endif %}
      {% if company.website %}<div>Website &nbsp;: {{ company.website }}</div>{% endif %}
    </td>
    <td style="width:20%; text-align:center; vertical-align:middle; padding:4px;">
      <img src=\"""" + LOGO_PATH + """\" style="max-height:75px; max-width:160px;">
    </td>
    <td style="width:40%; vertical-align:top; padding:4px 6px; direction:rtl; text-align:right;">
      <div style="font-weight:bold; font-size:11pt;">{{ company_ar }}</div>
      {% if address_ar %}<div style="white-space:pre-line;">{{ address_ar }}</div>{% endif %}
      <div>رقم الضريبة : {{ company.tax_id or "" }}</div>
      {% if cr_no %}<div>رقم سجل تجاري : {{ cr_no }}</div>{% endif %}
      {% if company.website %}<div>موقع الكتروني : {{ company.website }}</div>{% endif %}
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
        # Re-fill content only when empty — preserve manual edits.
        existing = frappe.db.get_value("Letter Head", MASTER_LETTER_HEAD, ["content", "image"], as_dict=True)
        if not (existing.content or "").strip():
            frappe.db.set_value("Letter Head", MASTER_LETTER_HEAD, {
                "content": LETTER_HEAD_HTML,
                "source": "HTML",
                "image": existing.image or LOGO_PATH,
            })

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
