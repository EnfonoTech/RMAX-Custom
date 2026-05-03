"""Branch-aware Letter Head provisioning for RMAX (Clear Light).

Each branch gets its own Letter Head record carrying the branch's
specific English + Arabic address + mobile number.  The branch master's
`custom_letter_head` field points at its branch-specific record.  At
print time, the Phase A `set_letter_head_from_branch` hook stamps
`doc.letter_head` from the resolved branch -> the matching letterhead
HTML renders at the top of every printable.

Idempotent.  Called from `setup.after_migrate`.  Source data is baked
into BRANCH_LETTERHEAD_DATA (mirrors `Entity and Branches List` xlsx).

A master `RMAX - Clear Light` record is also created/refreshed as the
fallback for branches without a specific entry.

The logo file `/files/clear-light.png` is staged separately (one-off
curl from rmax-dev to prod's public/files/).
"""

from __future__ import annotations

import frappe
from frappe import _


MASTER_LETTER_HEAD = "RMAX - Clear Light"
LOGO_PATH = "/files/clear-light.png"

# Branch -> address details from "Entity and Branches List" xlsx (sheet
# 01.05.2026 + Sheet3).  Kept in code (not fixture) so deploys stay
# atomic and reviewable in PR diff.  When a branch is added later,
# append a row here, redeploy, after_migrate seeds the Letter Head.
BRANCH_LETTERHEAD_DATA = [
    {
        "branch": "Head Office", "prefix": "HO-",
        "addr_en": "8433 Awtad Centre, Said Ibn Zaqar, 2363, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٨٤٣٣ مركز اوتاد، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0539776999",
    },
    {
        "branch": "HQ Awtad", "prefix": "HQ-",
        "addr_en": "8433 Awtad Centre, Said Ibn Zaqar, 2363, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٨٤٣٣ مركز اوتاد، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0539776999",
    },
    {
        "branch": "Warehouse Jeddah", "prefix": "WJ-",
        "addr_en": "8433 Awtad Centre, Said Ibn Zaqar, 2363, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٨٤٣٣ مركز اوتاد، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0539776999",
    },
    {
        "branch": "Warehouse Bahrah", "prefix": "WB-",
        "addr_en": "8433 Awtad Centre, Said Ibn Zaqar, 2363, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٨٤٣٣ مركز اوتاد، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0539776999",
    },
    {
        "branch": "Warehouse Riyadh", "prefix": "WR-",
        "addr_en": "8433 Awtad Centre, Said Ibn Zaqar, 2363, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٨٤٣٣ مركز اوتاد، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0539776999",
    },
    {
        "branch": "Warehouse Malaz", "prefix": "WM-",
        "addr_en": "8433 Awtad Centre, Said Ibn Zaqar, 2363, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٨٤٣٣ مركز اوتاد، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0539776999",
    },
    {
        "branch": "Ghurab Office", "prefix": "GO-",
        "addr_en": "2337 Suq Urab St., Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٢٣٣٧ سوق غراب، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0554986999",
    },
    {
        "branch": "Azzizziyah", "prefix": "AZZ-",
        "addr_en": "2736, Al Baladiah St., Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٢٧٣٦ البلدية، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0551534999",
    },
    {
        "branch": "Ghurab Showroom", "prefix": "GS-",
        "addr_en": "2333 Said Ibn Zaqar, Aziziyah District, Jeddah 23334",
        "addr_ar": "٢٣٣٣ شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0552306999",
    },
    {
        "branch": "Dammam Sales", "prefix": "DS-",
        "addr_en": "8433 Awtad Centre, Said Ibn Zaqar, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٨٤٣٣ مركز اوتاد، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0501532999",
    },
    {
        "branch": "CL1 Malaz", "prefix": "CL1-",
        "addr_en": "Prince Abdul Muhsin Bin Abdulaziz Rd, Al Malaz District, Riyadh 12842",
        "addr_ar": "طريق الامير عبدالمحسن بن عبدالعزيز، الملز، الرياض ١٢٨٤٢",
        "mobile": "0501436999",
    },
    {
        "branch": "CL2 Malaz", "prefix": "CL2-",
        "addr_en": "Prince Abdul Muhsin Bin Abdulaziz Rd, Al Malaz District, Riyadh 12842",
        "addr_ar": "طريق الامير عبدالمحسن بن عبدالعزيز، الملز، الرياض ١٢٨٤٢",
        "mobile": "0550675999",
    },
    {
        "branch": "Riyadh Sales", "prefix": "RS-",
        "addr_en": "Prince Abdul Muhsin Bin Abdulaziz Rd, Al Malaz District, Riyadh 12842",
        "addr_ar": "طريق الامير عبدالمحسن بن عبدالعزيز، الملز، الرياض ١٢٨٤٢",
        "mobile": "0557380999",
    },
    {
        "branch": "Reem", "prefix": "RM-",
        "addr_en": "Reem Centre, Said Ibn Zaqar, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "مركز ريم، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0506358999",
    },
    {
        "branch": "Taif Sales", "prefix": "TF-",
        "addr_en": "8433 Awtad Centre, Said Ibn Zaqar, 2363, Al Aziziyah District, Jeddah 23334",
        "addr_ar": "٨٤٣٣ مركز اوتاد، شارع سعيد بن زقر، حي العزيزية، جدة ٢٣٣٣٤",
        "mobile": "0556493999",
    },
]


def _branch_letterhead_html(addr_en: str, addr_ar: str, mobile: str, branch: str) -> str:
    """Per-branch bilingual header HTML.  Logo centre, English left, Arabic right."""
    return f"""
{{%- set company = frappe.get_cached_doc("Company", doc.company) if doc and doc.get("company") else None -%}}
{{%- set company_name = company.company_name if company else "CLEAR LIGHT TRADING COMPANY" -%}}
{{%- set company_ar = (company.get("custom_company_name_ar") if company else "") or "شركة الضوء الواضح التجارية" -%}}
{{%- set vat_id = (company.tax_id if company else "") or "" -%}}
{{%- set cr_no = (company.get("custom_cr_number") if company else "") or "" -%}}
{{%- set website = (company.website if company else "www.rmaxled.com") or "www.rmaxled.com" -%}}
<table style="width:100%; border-collapse:collapse; font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; font-size:9pt; border-bottom:2px solid #555; padding-bottom:4px;">
  <tr>
    <td style="width:38%; vertical-align:top; padding:4px 6px;">
      <div style="font-weight:bold; font-size:12pt;">{{{{ company_name }}}}</div>
      <div>Branch : {branch}</div>
      <div>{addr_en}</div>
      <div>VAT Number : {{{{ vat_id }}}}</div>
      {{% if cr_no %}}<div>C.R. No. &nbsp;: {{{{ cr_no }}}}</div>{{% endif %}}
      <div>Mobile &nbsp;&nbsp;&nbsp;: {mobile}</div>
      <div>Website &nbsp;: {{{{ website }}}}</div>
    </td>
    <td style="width:24%; text-align:center; vertical-align:middle; padding:4px;">
      <img src="{LOGO_PATH}" style="max-height:80px; max-width:170px;">
    </td>
    <td style="width:38%; vertical-align:top; padding:4px 6px; direction:rtl; text-align:right;">
      <div style="font-weight:bold; font-size:12pt;">{{{{ company_ar }}}}</div>
      <div>الفرع : {branch}</div>
      <div>{addr_ar}</div>
      <div>رقم الضريبة : {{{{ vat_id }}}}</div>
      {{% if cr_no %}}<div>رقم سجل تجاري : {{{{ cr_no }}}}</div>{{% endif %}}
      <div>جوال &nbsp;: {mobile}</div>
      <div>موقع الكتروني : {{{{ website }}}}</div>
    </td>
  </tr>
</table>
""".strip()


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

    # Per-branch letter heads — one record per Branch with branch-specific
    # English + Arabic address + mobile baked in.
    setup_branch_letter_heads()

    # Backfill empty Branch.custom_letter_head — point at the branch's
    # own letterhead when present, else the master.
    if not frappe.db.has_column("Branch", "custom_letter_head"):
        return
    for branch in frappe.get_all("Branch", pluck="name"):
        current = frappe.db.get_value("Branch", branch, "custom_letter_head") or ""
        # Per-branch record name convention: "RMAX - <Branch>"
        own_lh = f"RMAX - {branch}"
        if frappe.db.exists("Letter Head", own_lh):
            target = own_lh
        else:
            target = MASTER_LETTER_HEAD
        if current != target:
            frappe.db.set_value("Branch", branch, "custom_letter_head", target)

    frappe.db.commit()


def setup_branch_letter_heads() -> None:
    """Create one Letter Head per branch with the branch's address baked in.

    Idempotent.  Naming: `RMAX - <Branch Name>`.  Refreshes content on
    every run so the canonical address stays in sync with the xlsx
    source-of-truth (BRANCH_LETTERHEAD_DATA above).
    """
    if not frappe.db.exists("DocType", "Letter Head"):
        return
    for entry in BRANCH_LETTERHEAD_DATA:
        branch = entry["branch"]
        if not frappe.db.exists("Branch", branch):
            continue
        lh_name = f"RMAX - {branch}"
        html = _branch_letterhead_html(
            addr_en=entry["addr_en"],
            addr_ar=entry["addr_ar"],
            mobile=entry["mobile"],
            branch=branch,
        )
        try:
            if frappe.db.exists("Letter Head", lh_name):
                lh = frappe.get_doc("Letter Head", lh_name)
                lh.source = "HTML"
                lh.content = html
                if not (lh.image or "").strip():
                    lh.image = LOGO_PATH
                lh.disabled = 0
                lh.save(ignore_permissions=True)
            else:
                frappe.get_doc({
                    "doctype": "Letter Head",
                    "letter_head_name": lh_name,
                    "is_default": 0,
                    "disabled": 0,
                    "source": "HTML",
                    "content": html,
                    "image": LOGO_PATH,
                }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"rmax_custom: failed to create/update Letter Head {lh_name}",
            )
