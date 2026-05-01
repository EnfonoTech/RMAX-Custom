"""
Build RMAX Print Format JSON files from inline Jinja templates.

Run from repo root after editing any of the inline TEMPLATE strings:

    python scripts/build_print_formats.py

Outputs four standard Print Format JSONs under:
    rmax_custom/rmax_custom/print_format/<snake_name>/<snake_name>.json

These are loaded by `bench migrate` (because each lives in a module
print_format folder with `standard: "Yes"`).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PF_DIR = ROOT / "rmax_custom" / "rmax_custom" / "print_format"


def make_pf(name: str, doc_type: str, html: str, css: str = "") -> dict:
    return {
        "align_labels_right": 0,
        "absolute_value": 0,
        "custom_format": 1,
        "default_print_language": "en",
        "disabled": 0,
        "doc_type": doc_type,
        "docstatus": 0,
        "doctype": "Print Format",
        "font": "Default",
        "font_size": 9,
        "html": html,
        "css": css,
        "line_breaks": 0,
        "margin_bottom": 10.0,
        "margin_left": 10.0,
        "margin_right": 10.0,
        "margin_top": 10.0,
        "modified": "2026-05-01 12:00:00.000000",
        "module": "Rmax Custom",
        "name": name,
        "page_number": "Hide",
        "print_format_builder": 0,
        "print_format_builder_beta": 0,
        "print_format_type": "Jinja",
        "show_section_headings": 0,
        "standard": "Yes",
    }


# ---------------------------------------------------------------------------
# Shared CSS
# ---------------------------------------------------------------------------

SHARED_CSS = """
.rmax-print { font-family: 'Helvetica Neue', Arial, 'Tahoma', sans-serif; font-size: 9pt; color: #000; }
.rmax-print table { width: 100%; border-collapse: collapse; }
.rmax-print td, .rmax-print th { padding: 3px 5px; vertical-align: top; }
.rmax-bordered td, .rmax-bordered th { border: 1px solid #333; }
.rmax-header td { border: none; }
.rmax-title-bar { background: #f3f3f3; border: 1px solid #333; padding: 6px; font-size: 14pt; text-align: center; font-weight: bold; }
.rmax-section-label { background: #efefef; font-weight: bold; padding: 4px 6px; border: 1px solid #333; }
.rmax-rtl { direction: rtl; text-align: right; }
.rmax-ltr { direction: ltr; text-align: left; }
.rmax-center { text-align: center; }
.rmax-right { text-align: right; }
.rmax-bold { font-weight: bold; }
.rmax-small { font-size: 8pt; }
.rmax-items th { background: #f3f3f3; font-weight: bold; text-align: center; font-size: 8.5pt; }
.rmax-items td { font-size: 9pt; }
.rmax-totals td { font-weight: bold; }
.rmax-qr { width: 110px; height: 110px; }
.rmax-logo { max-height: 70px; }
.rmax-signature-box { border: 1px solid #333; padding: 6px; min-height: 70px; }
@media print { .rmax-print { font-size: 9pt; } }
"""

# ---------------------------------------------------------------------------
# 1) RMAX Tax Invoice  (Sales Invoice — handles both invoice + return)
# ---------------------------------------------------------------------------

TAX_INVOICE_HTML = r"""{%- set company = frappe.get_cached_doc("Company", doc.company) -%}
{%- set company_ar = company.get("custom_company_name_ar") or company.company_name -%}
{%- set address_ar = company.get("custom_address_block_ar") or "" -%}
{%- set cr_no = company.get("custom_cr_number") or "" -%}
{%- set bank_accounts = get_rmax_company_bank_accounts(doc.company) -%}
{%- set zatca_qr = get_rmax_zatca_qr(doc) -%}
{%- set co_address = get_rmax_company_address(doc.company) -%}
{%- set customer_phone = get_rmax_customer_phone(doc) -%}
{%- set is_return = doc.is_return == 1 -%}
{%- set title_en = "CASH RETURN" if is_return else "TAX INVOICE" -%}
{%- set title_ar = "مرتجع نقدي" if is_return else "فاتورة ضريبية" -%}
{%- set print_logo = company.get("custom_print_logo") or company.company_logo or "" -%}
{%- set prepared_by_name = frappe.db.get_value("User", doc.owner, "full_name") or doc.owner -%}
{%- set prepared_by_mobile = frappe.db.get_value("User", doc.owner, "mobile_no") or "" -%}

<div class="rmax-print">

<table class="rmax-header">
  <tr>
    <td style="width:40%; vertical-align:top;">
      <div class="rmax-bold" style="font-size:11pt;">{{ company.company_name }}</div>
      {% if co_address %}
        <div class="rmax-small">{{ co_address.address_line1 or "" }}</div>
        {% if co_address.address_line2 %}<div class="rmax-small">{{ co_address.address_line2 }}</div>{% endif %}
        <div class="rmax-small">{{ co_address.city or "" }}{% if co_address.pincode %} - {{ co_address.pincode }}{% endif %}{% if co_address.country %}, {{ co_address.country }}{% endif %}</div>
      {% endif %}
      <div class="rmax-small">VAT Number : {{ company.tax_id or "" }}</div>
      {% if cr_no %}<div class="rmax-small">C.R. No. &nbsp;&nbsp;: {{ cr_no }}</div>{% endif %}
      {% if company.website %}<div class="rmax-small">Website &nbsp;: {{ company.website }}</div>{% endif %}
    </td>
    <td style="width:20%; text-align:center; vertical-align:middle;">
      {% if print_logo %}<img src="{{ print_logo }}" class="rmax-logo">{% endif %}
    </td>
    <td style="width:40%; vertical-align:top;" class="rmax-rtl">
      <div class="rmax-bold" style="font-size:11pt;">{{ company_ar }}</div>
      {% if address_ar %}<div class="rmax-small" style="white-space:pre-line;">{{ address_ar }}</div>{% endif %}
      <div class="rmax-small">رقم الضريبة : {{ company.tax_id or "" }}</div>
      {% if cr_no %}<div class="rmax-small">رقم سجل تجاري : {{ cr_no }}</div>{% endif %}
      {% if company.website %}<div class="rmax-small">موقع الكتروني : {{ company.website }}</div>{% endif %}
    </td>
  </tr>
</table>

<div class="rmax-title-bar" style="margin-top:6px;">
  {{ title_en }} - {{ title_ar }}
  <span style="float:right; font-size:9pt; font-weight:normal;">Page <span class="page"></span> of <span class="topage"></span></span>
</div>

<table class="rmax-bordered" style="margin-top:6px;">
  <tr>
    <td style="width:18%;" class="rmax-bold">Invoice Number</td>
    <td style="width:32%;">: {{ doc.name }}</td>
    <td style="width:32%;" class="rmax-rtl">{{ doc.name }} :</td>
    <td style="width:18%;" class="rmax-rtl rmax-bold">رقم الفاتورة</td>
  </tr>
  <tr>
    <td class="rmax-bold">Invoice Issue Date</td>
    <td>: {{ doc.get_formatted("posting_date") }}</td>
    <td class="rmax-rtl">{{ doc.get_formatted("posting_date") }} :</td>
    <td class="rmax-rtl rmax-bold">تاريخ إصدار الفاتورة</td>
  </tr>
  <tr>
    <td class="rmax-bold">Invoice Issue Time</td>
    <td>: {{ doc.get_formatted("posting_time") }}</td>
    <td class="rmax-rtl">{{ doc.get_formatted("posting_time") }} :</td>
    <td class="rmax-rtl rmax-bold">وقت إصدار الفاتورة</td>
  </tr>
</table>

<table class="rmax-bordered" style="margin-top:6px;">
  <tr>
    <td colspan="2" class="rmax-section-label">Buyer</td>
    <td colspan="2" class="rmax-section-label rmax-rtl">المشترى</td>
  </tr>
  {% set cust = frappe.get_cached_doc("Customer", doc.customer) %}
  {% set cust_addr = frappe.db.get_value("Address", doc.customer_address, ["address_line1","address_line2","city","pincode"], as_dict=True) if doc.customer_address else None %}
  <tr>
    <td style="width:14%;" class="rmax-bold">Name</td>
    <td style="width:36%;">: {{ doc.customer_name or doc.customer }}</td>
    <td style="width:36%;" class="rmax-rtl">{{ doc.customer_name or doc.customer }} :</td>
    <td style="width:14%;" class="rmax-rtl rmax-bold">الإسم</td>
  </tr>
  <tr>
    <td class="rmax-bold">Address</td>
    <td>: {% if cust_addr %}{{ cust_addr.address_line1 or "" }}{% if cust_addr.city %}, {{ cust_addr.city }}{% endif %}{% endif %}</td>
    <td class="rmax-rtl">{% if cust_addr %}{{ cust_addr.address_line1 or "" }}{% if cust_addr.city %}, {{ cust_addr.city }}{% endif %}{% endif %} :</td>
    <td class="rmax-rtl rmax-bold">عنوان</td>
  </tr>
  <tr>
    <td class="rmax-bold">VAT Number</td>
    <td>: {{ cust.tax_id or cust.get("custom_vat_registration_number") or "" }}</td>
    <td class="rmax-rtl">{{ cust.tax_id or cust.get("custom_vat_registration_number") or "" }} :</td>
    <td class="rmax-rtl rmax-bold">رقم الضريبة</td>
  </tr>
  <tr>
    <td class="rmax-bold">Phone</td>
    <td>: {{ customer_phone }}</td>
    <td class="rmax-rtl">{{ customer_phone }} :</td>
    <td class="rmax-rtl rmax-bold">هاتف</td>
  </tr>
</table>

<table class="rmax-bordered rmax-items" style="margin-top:6px;">
  <thead>
    <tr>
      <th rowspan="2" style="width:3%;">Sl.<br>الرقم</th>
      <th rowspan="2" style="width:11%;">Item Code<br>رقم الصنف</th>
      <th rowspan="2" style="width:24%;">Nature of Goods or Services<br>تفاصيل السلع أو الخدمات</th>
      <th rowspan="2" style="width:6%;">Qty.<br>الكمية</th>
      <th rowspan="2" style="width:9%;">Unit Price<br>سعر الوحدة</th>
      <th rowspan="2" style="width:7%;">Discount<br>خصم</th>
      <th rowspan="2" style="width:10%;">Taxable Amt.<br>المبلغ الخاضع للضريبة</th>
      <th rowspan="2" style="width:6%;">VAT %<br>ضريبة %</th>
      <th rowspan="2" style="width:9%;">VAT Amt.<br>قيمه الضريبه</th>
      <th rowspan="2" style="width:11%;">Inv. Amt. Incl. VAT<br>مبلغ الفواتير يشمل الضريبة</th>
    </tr>
  </thead>
  <tbody>
    {% for row in doc.items %}
      {% set qty = row.qty | abs %}
      {% set unit_price = row.rate | abs %}
      {% set discount = (row.discount_amount or 0) * qty %}
      {% set net_amt = row.net_amount | abs %}
      {% set vat_pct = row.get("tax_rate") or 0 %}
      {% set vat_amt = (row.get("total_vat_linewise") or row.get("tax_amount") or (net_amt * vat_pct / 100)) | abs %}
      {% set incl = net_amt + vat_amt %}
      <tr>
        <td class="rmax-center">{{ row.idx }}</td>
        <td>{{ row.item_code }}</td>
        <td>{{ row.item_name }}</td>
        <td class="rmax-right">{{ "{:.0f}".format(qty) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(unit_price) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(discount) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(net_amt) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(vat_pct) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(vat_amt) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(incl) }}</td>
      </tr>
    {% endfor %}
  </tbody>
</table>

<table style="margin-top:6px;">
  <tr>
    <td style="width:25%; vertical-align:top; text-align:center;">
      {% if zatca_qr %}<img src="{{ zatca_qr }}" class="rmax-qr">{% endif %}
    </td>
    <td style="vertical-align:top;">
      <table class="rmax-bordered rmax-totals">
        <tr><td colspan="3" class="rmax-section-label">Total Amounts <span class="rmax-rtl" style="float:right;">إجمالي المبالغ</span></td></tr>
        <tr>
          <td style="width:35%;">Total (Excluding VAT)</td>
          <td class="rmax-rtl" style="width:45%;">الإجمالي (قبل ضريبة القيمة المضافة)</td>
          <td class="rmax-right" style="width:20%;">{{ "{:.2f}".format(doc.net_total | abs) }}</td>
        </tr>
        <tr>
          <td>Discount</td>
          <td class="rmax-rtl">الخصم</td>
          <td class="rmax-right">{{ "{:.2f}".format(doc.discount_amount | abs) }}</td>
        </tr>
        <tr>
          <td>Total Taxable Amount</td>
          <td class="rmax-rtl">إجمالي المبلغ الخاضع للضريبة</td>
          <td class="rmax-right">{{ "{:.2f}".format((doc.net_total - (doc.discount_amount or 0)) | abs) }}</td>
        </tr>
        <tr>
          <td>Total VAT</td>
          <td class="rmax-rtl">إجمالي مبلغ ضريبة القيمة المضافة</td>
          <td class="rmax-right">{{ "{:.2f}".format(doc.total_taxes_and_charges | abs) }}</td>
        </tr>
        <tr class="rmax-bold">
          <td>Total Amount Due in SAR</td>
          <td class="rmax-rtl">المبلغ الإجمالي المستحق بالريال السعودي</td>
          <td class="rmax-right">{{ "{:.2f}".format(doc.grand_total | abs) }}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>

<table style="margin-top:10px;">
  <tr>
    <td style="width:25%;"><span class="rmax-bold">Prepared By :</span> {{ prepared_by_name }}</td>
    <td style="width:25%;"><span class="rmax-bold">Mobile :</span> {{ prepared_by_mobile }}</td>
    <td style="width:25%;"><span class="rmax-bold">Approved By :</span></td>
    <td style="width:25%;" class="rmax-rtl"><span class="rmax-bold">: تمت الموافقة من قبل</span></td>
  </tr>
</table>

{% if bank_accounts %}
<table style="margin-top:8px;">
  <tr>
    {% for ba in bank_accounts %}
      <td style="width:{{ (100 / bank_accounts|length) | round(0,'floor') | int }}%;">
        <span class="rmax-bold">Bank {{ ba.bank }} :</span>
        {{ ba.iban or "-" }}{% if ba.bank_account_no %} - {{ ba.bank_account_no }}{% endif %}
      </td>
    {% endfor %}
  </tr>
</table>
{% endif %}

</div>
"""


# ---------------------------------------------------------------------------
# 2) RMAX Quotation
# ---------------------------------------------------------------------------

QUOTATION_HTML = r"""{%- set company = frappe.get_cached_doc("Company", doc.company) -%}
{%- set company_ar = company.get("custom_company_name_ar") or company.company_name -%}
{%- set address_ar = company.get("custom_address_block_ar") or "" -%}
{%- set print_logo = company.get("custom_print_logo") or company.company_logo or "" -%}
{%- set prepared_by_name = frappe.db.get_value("User", doc.owner, "full_name") or doc.owner -%}

<div class="rmax-print">

<table class="rmax-header">
  <tr>
    <td style="width:25%; vertical-align:middle;">
      {% if print_logo %}<img src="{{ print_logo }}" class="rmax-logo">{% endif %}
    </td>
    <td style="vertical-align:top;" class="rmax-rtl">
      <div class="rmax-bold" style="font-size:13pt;">{{ company_ar }}</div>
      {% if address_ar %}<div class="rmax-small" style="white-space:pre-line;">{{ address_ar }}</div>{% endif %}
      <div class="rmax-small">رقم ضريبي : {{ company.tax_id or "" }}</div>
      <div class="rmax-small">E-mail : {{ company.email or "" }} &nbsp; Website : {{ company.website or "" }}</div>
    </td>
  </tr>
</table>

<div class="rmax-title-bar rmax-center" style="margin-top:6px; background:transparent; border:none; font-size:14pt;">Quotation</div>
<div style="text-align:right; font-size:8.5pt;">
  Info. : {{ frappe.utils.format_datetime(frappe.utils.now(), "dd-MMM-yyyy HH:mm") }} &nbsp; {{ prepared_by_name }} &nbsp;
  Page <span class="page"></span> of <span class="topage"></span>
</div>

<table style="margin-top:6px;">
  <tr>
    <td style="width:14%;" class="rmax-bold">Branch</td>
    <td style="width:36%;">: {{ doc.branch or "" }}</td>
    <td style="width:14%;" class="rmax-bold">Quotation No.</td>
    <td style="width:36%;">: {{ doc.name }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Customer</td>
    <td>: {{ doc.party_name or "" }} &nbsp;&nbsp; {{ doc.customer_name or "" }}</td>
    <td class="rmax-bold">Date</td>
    <td>: {{ doc.get_formatted("transaction_date") }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Address</td>
    <td>: {% if doc.customer_address %}{{ frappe.db.get_value("Address", doc.customer_address, "address_line1") or "" }}{% endif %}</td>
    <td class="rmax-bold">Revision Date</td>
    <td>: {% if doc.valid_till %}{{ doc.get_formatted("valid_till") }}{% endif %}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Phone</td>
    <td>: {% if doc.contact_person %}{{ frappe.db.get_value("Contact", doc.contact_person, "mobile_no") or "" }}{% endif %}</td>
    <td class="rmax-bold">Contact Name</td>
    <td>: {{ doc.contact_display or "" }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Delivery Terms</td>
    <td>: {{ doc.tc_name or "" }}</td>
    <td class="rmax-bold">Customer Ref.</td>
    <td>: {{ doc.get("custom_customer_po_no") or "" }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Payment Terms</td>
    <td colspan="3">: {{ doc.payment_terms_template or "" }}</td>
  </tr>
</table>

<table class="rmax-bordered rmax-items" style="margin-top:6px;">
  <thead>
    <tr>
      <th style="width:4%;">Sl. #</th>
      <th style="width:14%;">Item ID</th>
      <th style="width:36%;">Item Name</th>
      <th style="width:6%;">Unit</th>
      <th style="width:8%;">Qty.</th>
      <th style="width:10%;">Unit Price</th>
      <th style="width:9%;">Discount</th>
      <th style="width:13%;">Total Price</th>
    </tr>
  </thead>
  <tbody>
    {% set ns = namespace(total_qty=0, total_amt=0) %}
    {% for row in doc.items %}
      {% set ns.total_qty = ns.total_qty + (row.qty | float) %}
      {% set ns.total_amt = ns.total_amt + (row.amount | float) %}
      <tr>
        <td class="rmax-center">{{ row.idx }}</td>
        <td>{{ row.item_code }}</td>
        <td>{{ row.item_name }}</td>
        <td class="rmax-center">{{ row.uom or "" }}</td>
        <td class="rmax-right">{{ "{:.0f}".format(row.qty) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(row.rate) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(row.discount_amount or 0) }}</td>
        <td class="rmax-right">{{ "{:.2f}".format(row.amount) }}</td>
      </tr>
    {% endfor %}
    <tr class="rmax-bold">
      <td colspan="4" class="rmax-right">Total :</td>
      <td class="rmax-right">{{ "{:.0f}".format(ns.total_qty) }}</td>
      <td colspan="2"></td>
      <td class="rmax-right">{{ "{:.2f}".format(ns.total_amt) }}</td>
    </tr>
  </tbody>
</table>

<table style="margin-top:6px; width:50%; float:right;" class="rmax-bordered rmax-totals">
  <tr><td>Discount :</td><td class="rmax-right">{{ "{:.2f}".format(doc.discount_amount or 0) }}</td></tr>
  <tr><td>Net Amt. Excl. VAT :</td><td class="rmax-right">{{ "{:.2f}".format(doc.net_total) }}</td></tr>
  <tr><td>VAT :</td><td class="rmax-right">{{ "{:.2f}".format(doc.total_taxes_and_charges or 0) }}</td></tr>
  <tr class="rmax-bold"><td>Net Amt. Incl. VAT :</td><td class="rmax-right">{{ "{:.2f}".format(doc.grand_total) }}</td></tr>
</table>

<div style="clear:both;"></div>

<div style="margin-top:10px;"><span class="rmax-bold">Note :</span> {{ doc.terms or "" }}</div>

</div>
"""


# ---------------------------------------------------------------------------
# 3) RMAX Delivery Note
# ---------------------------------------------------------------------------

DELIVERY_NOTE_HTML = r"""{%- set company = frappe.get_cached_doc("Company", doc.company) -%}
{%- set print_logo = company.get("custom_print_logo") or company.company_logo or "" -%}

<div class="rmax-print">

<table class="rmax-header">
  <tr>
    <td style="width:30%; vertical-align:middle;">
      {% if print_logo %}<img src="{{ print_logo }}" class="rmax-logo">{% endif %}
    </td>
    <td style="vertical-align:middle; font-size:16pt;" class="rmax-bold">Delivery Note</td>
  </tr>
</table>

<table class="rmax-bordered" style="margin-top:6px;">
  <tr>
    <td style="width:14%;" class="rmax-bold">Date</td>
    <td style="width:36%;">: {{ doc.get_formatted("posting_date") }}</td>
    <td style="width:18%;" class="rmax-bold">Delivery Note No.</td>
    <td style="width:32%;">: {{ doc.name }}</td>
  </tr>
  <tr>
    <td colspan="4" class="rmax-section-label">CUSTOMER DETAILS</td>
  </tr>
  <tr>
    <td class="rmax-bold">Name</td>
    <td colspan="3">: {{ doc.contact_display or "" }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Company Name</td>
    <td colspan="3">: {{ doc.customer_name or doc.customer }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Customer ID</td>
    <td colspan="3">: {{ doc.customer }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Customer P.O No.</td>
    <td colspan="3">: {{ doc.po_no or "" }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Address</td>
    <td colspan="3">: {% if doc.shipping_address %}{{ doc.shipping_address|striptags|replace('\n',' ') }}{% elif doc.customer_address %}{{ frappe.db.get_value("Address", doc.customer_address, "address_line1") or "" }}{% endif %}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Contact Number</td>
    <td colspan="3">: {{ doc.contact_mobile or "" }}</td>
  </tr>
</table>

<table class="rmax-bordered rmax-items" style="margin-top:6px;">
  <thead>
    <tr>
      <th style="width:6%;">SN</th>
      <th style="width:18%;">Item Code</th>
      <th style="width:54%;">Description</th>
      <th style="width:10%;">Unit</th>
      <th style="width:12%;">Quantity</th>
    </tr>
  </thead>
  <tbody>
    {% set ns = namespace(total_qty=0) %}
    {% for row in doc.items %}
      {% set ns.total_qty = ns.total_qty + (row.qty | float) %}
      <tr>
        <td class="rmax-center">{{ row.idx }}</td>
        <td>{{ row.item_code }}</td>
        <td>{{ row.item_name }}</td>
        <td class="rmax-center">{{ row.uom or "" }}</td>
        <td class="rmax-right">{{ "{:.0f}".format(row.qty) }}</td>
      </tr>
    {% endfor %}
    <tr class="rmax-bold">
      <td colspan="4" class="rmax-right">Total :</td>
      <td class="rmax-right">{{ "{:.0f}".format(ns.total_qty) }}</td>
    </tr>
  </tbody>
</table>

<table style="margin-top:30px;">
  <tr>
    <td style="width:50%; padding-right:10px;">
      <div class="rmax-bold">Delivered By :</div>
      <div class="rmax-signature-box">
        <div>Name</div>
        <div style="margin-top:18px;">Signature</div>
        <div style="margin-top:18px;">Date</div>
      </div>
    </td>
    <td style="width:50%; padding-left:10px;">
      <div class="rmax-bold">Received By :</div>
      <div class="rmax-signature-box">
        <div>Name</div>
        <div style="margin-top:18px;">Signature</div>
        <div style="margin-top:18px;">Date</div>
      </div>
    </td>
  </tr>
</table>

</div>
"""


# ---------------------------------------------------------------------------
# 4) RMAX Purchase Order
# ---------------------------------------------------------------------------

PURCHASE_ORDER_HTML = r"""{%- set company = frappe.get_cached_doc("Company", doc.company) -%}
{%- set company_ar = company.get("custom_company_name_ar") or company.company_name -%}
{%- set address_ar = company.get("custom_address_block_ar") or "" -%}
{%- set print_logo = company.get("custom_print_logo") or company.company_logo or "" -%}
{%- set prepared_by_name = frappe.db.get_value("User", doc.owner, "full_name") or doc.owner -%}

<div class="rmax-print">

<table class="rmax-header">
  <tr>
    <td style="width:25%; vertical-align:middle;">
      {% if print_logo %}<img src="{{ print_logo }}" class="rmax-logo">{% endif %}
    </td>
    <td style="vertical-align:top;" class="rmax-rtl">
      <div class="rmax-bold" style="font-size:13pt;">{{ company_ar }}</div>
      {% if address_ar %}<div class="rmax-small" style="white-space:pre-line;">{{ address_ar }}</div>{% endif %}
      <div class="rmax-small">رقم ضريبي : {{ company.tax_id or "" }}</div>
      <div class="rmax-small">E-mail : {{ company.email or "" }} &nbsp; Website : {{ company.website or "" }}</div>
    </td>
  </tr>
</table>

<div class="rmax-title-bar rmax-center" style="margin-top:6px; background:transparent; border:none; font-size:14pt;">Purchase Order</div>
<div style="text-align:right; font-size:8.5pt;">
  Info. : {{ frappe.utils.format_datetime(frappe.utils.now(), "dd-MMM-yyyy HH:mm") }} &nbsp; {{ prepared_by_name }} &nbsp;
  Page <span class="page"></span> of <span class="topage"></span>
</div>

<table style="margin-top:6px;">
  <tr>
    <td style="width:14%;" class="rmax-bold">Branch</td>
    <td style="width:36%;">: {{ doc.branch or "" }}</td>
    <td style="width:14%;" class="rmax-bold">P.O. No.</td>
    <td style="width:36%;">: {{ doc.name }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Date</td>
    <td>: {{ doc.get_formatted("transaction_date") }}</td>
    <td class="rmax-bold">Supplier</td>
    <td>: {{ doc.supplier }} &nbsp;&nbsp; {{ doc.supplier_name or "" }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Supplier Ref</td>
    <td>: {{ doc.supplier_quotation or "" }}</td>
    <td class="rmax-bold">CUR.</td>
    <td>: {{ doc.currency }} &nbsp;&nbsp; <span class="rmax-bold">Currency Rate :</span> {{ "{:.4f}".format(doc.conversion_rate or 1) }}</td>
  </tr>
  <tr>
    <td class="rmax-bold">Payment Terms</td>
    <td>: {{ doc.payment_terms_template or "" }}</td>
    <td class="rmax-bold">Delivery Terms</td>
    <td>: {{ doc.tc_name or "" }}</td>
  </tr>
</table>

<table class="rmax-bordered rmax-items" style="margin-top:6px;">
  <thead>
    <tr>
      <th style="width:4%;">Sl. #</th>
      <th style="width:14%;">Item ID</th>
      <th style="width:34%;">Item Name</th>
      <th style="width:6%;">Unit</th>
      <th style="width:8%;">Packing</th>
      <th style="width:8%;">Qty.</th>
      <th style="width:12%;">Unit Price</th>
      <th style="width:14%;">Total Price</th>
    </tr>
  </thead>
  <tbody>
    {% set ns = namespace(total_qty=0, total_amt=0) %}
    {% for row in doc.items %}
      {% set ns.total_qty = ns.total_qty + (row.qty | float) %}
      {% set ns.total_amt = ns.total_amt + (row.amount | float) %}
      <tr>
        <td class="rmax-center">{{ row.idx }}</td>
        <td>{{ row.item_code }}</td>
        <td>{{ row.item_name }}</td>
        <td class="rmax-center">{{ row.uom or "" }}</td>
        <td class="rmax-right">{{ "{:.0f}".format(row.conversion_factor or 0) }}</td>
        <td class="rmax-right">{{ "{:.0f}".format(row.qty) }}</td>
        <td class="rmax-right">{{ "{:.4f}".format(row.rate) }}</td>
        <td class="rmax-right">{{ "{:.4f}".format(row.amount) }}</td>
      </tr>
    {% endfor %}
    <tr class="rmax-bold">
      <td colspan="5" class="rmax-right">Total :</td>
      <td class="rmax-right">{{ "{:.0f}".format(ns.total_qty) }}</td>
      <td></td>
      <td class="rmax-right">{{ "{:.4f}".format(ns.total_amt) }}</td>
    </tr>
  </tbody>
</table>

<div style="margin-top:10px;"><span class="rmax-bold">Note :</span> {{ doc.terms or "" }}</div>

</div>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FORMATS = [
    ("RMAX Tax Invoice",     "Sales Invoice",  "rmax_tax_invoice",     TAX_INVOICE_HTML),
    ("RMAX Quotation",       "Quotation",      "rmax_quotation",       QUOTATION_HTML),
    ("RMAX Delivery Note",   "Delivery Note",  "rmax_delivery_note",   DELIVERY_NOTE_HTML),
    ("RMAX Purchase Order",  "Purchase Order", "rmax_purchase_order",  PURCHASE_ORDER_HTML),
]


def main() -> None:
    PF_DIR.mkdir(parents=True, exist_ok=True)
    for display_name, doc_type, snake, html in FORMATS:
        d = PF_DIR / snake
        d.mkdir(parents=True, exist_ok=True)
        (d / "__init__.py").touch(exist_ok=True)
        out = d / f"{snake}.json"
        payload = make_pf(display_name, doc_type, html, SHARED_CSS)
        with out.open("w") as f:
            json.dump(payload, f, indent=1, sort_keys=False, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
