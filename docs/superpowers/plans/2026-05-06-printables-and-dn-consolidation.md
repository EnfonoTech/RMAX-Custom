# Printables, Branch User SI Tuning, DN+Return Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the four-section client-requested change set from `Printables Status Branch Address and Mobile Number.docx`: bilingual ZATCA print format with B2C "Simplified Tax Invoice" mode, Branch User Sales Invoice form tuning, mixed DN + Return DN net-off consolidation into a single Sales Invoice, and DN source warehouse auto-fill.

**Architecture:** Six independently-shippable phases. Phase 1 lays the shared Custom Fields + Property Setter foundation used by Phases 2 and 3. Phase 4 (consolidation) is the largest, with a new whitelisted API (`consolidate_dns_to_si`) plus a refactor that extracts the existing inter-company SI builder into a shared helper so both modes (positive-only and net-off) share one implementation. Phase 5 polishes DN form ergonomics. Phase 6 is the deploy gate across DEV/UAT/PROD with explicit verification steps for each acceptance criterion.

**Tech Stack:** Frappe v15, ERPNext v15, Python 3.10+, vanilla JS for client extensions, wkhtmltopdf 0.12.6 for print rendering, pytest-style Frappe test runner (`bench run-tests`), Bash + supervisorctl for deploys.

**Spec:** `docs/superpowers/specs/2026-05-06-printables-and-dn-consolidation-design.md`

**Source artefacts:**
- IMG-1 mockup: `/tmp/docx_printables/media/image.jpg` (10 MB, hand-marked Tax Invoice)
- IMG-2 SI form X-marks: `/tmp/docx_printables/media/image2.jpg`
- IMG-3 SI Taxes section circled: `/tmp/docx_printables/media/image3.jpg`

---

## Pre-flight

- [ ] **Pre-1: Verify clean working tree on feature branch**

```bash
cd /Users/sayanthns/Documents/RMAX/RMAX-Custom
git status
git checkout -b feature/printables-and-consolidation main
```

Expected: working tree clean, on new branch `feature/printables-and-consolidation`.

- [ ] **Pre-2: Confirm dev site is reachable and migrate-clean**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 console <<< 'print(\"OK\")'"
```

Expected: `OK` in stdout, no traceback.

- [ ] **Pre-3: Snapshot current print_format JSONs for diff later**

```bash
mkdir -p /tmp/print_format_snapshot
cp -r rmax_custom/rmax_custom/print_format/rmax_tax_invoice_zatca /tmp/print_format_snapshot/
cp -r rmax_custom/rmax_custom/print_format/rmax_tax_invoice /tmp/print_format_snapshot/
```

Expected: both folders present in snapshot.

---

## Phase 1 — Custom Fields + Property Setters Foundation

Adds the underlying schema (Customer, Address, Delivery Note custom fields; Customer search field PS) used by Phases 2, 3, and 4.

### Task 1.1: Customer Arabic + B2C Custom Fields

**Files:**
- Modify: `rmax_custom/fixtures/custom_field.json`
- Modify: `rmax_custom/hooks.py` (fixtures filter list — only if doctype not already covered)

- [ ] **Step 1: Add Customer custom field rows to fixture JSON**

Append to `rmax_custom/fixtures/custom_field.json` (within the existing top-level array, before the closing `]`):

```json
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "default": null,
 "depends_on": null,
 "description": "Customer name in Arabic. Used by ZATCA Tax Invoice print format and Customer search.",
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Customer",
 "fetch_from": null,
 "fetch_if_empty": 0,
 "fieldname": "custom_customer_name_ar",
 "fieldtype": "Data",
 "hidden": 0,
 "hide_border": 0,
 "hide_days": 0,
 "hide_seconds": 0,
 "ignore_user_permissions": 0,
 "ignore_xss_filter": 0,
 "in_filter": 0,
 "in_global_search": 1,
 "in_list_view": 0,
 "in_preview": 0,
 "in_standard_filter": 0,
 "insert_after": "customer_name",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Customer Name (Arabic)",
 "length": 0,
 "mandatory_depends_on": null,
 "modified": "2026-05-06 10:00:00.000000",
 "module": "Rmax Custom",
 "name": "Customer-custom_customer_name_ar",
 "no_copy": 0,
 "non_negative": 0,
 "options": null,
 "permlevel": 0,
 "precision": "",
 "print_hide": 0,
 "print_hide_if_no_value": 0,
 "print_width": null,
 "read_only": 0,
 "read_only_depends_on": null,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "show_dashboard": 0,
 "translatable": 0,
 "unique": 0,
 "width": null
},
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "default": null,
 "depends_on": null,
 "description": "Mobile number formatted for Arabic locale. Optional — falls back to mobile_no if blank.",
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Customer",
 "fetch_from": null,
 "fetch_if_empty": 0,
 "fieldname": "custom_mobile_ar",
 "fieldtype": "Data",
 "hidden": 0,
 "hide_border": 0,
 "hide_days": 0,
 "hide_seconds": 0,
 "ignore_user_permissions": 0,
 "ignore_xss_filter": 0,
 "in_filter": 0,
 "in_global_search": 0,
 "in_list_view": 0,
 "in_preview": 0,
 "in_standard_filter": 0,
 "insert_after": "mobile_no",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Mobile (Arabic)",
 "length": 0,
 "mandatory_depends_on": null,
 "modified": "2026-05-06 10:00:00.000000",
 "module": "Rmax Custom",
 "name": "Customer-custom_mobile_ar",
 "no_copy": 0,
 "non_negative": 0,
 "options": null,
 "permlevel": 0,
 "precision": "",
 "print_hide": 0,
 "print_hide_if_no_value": 0,
 "print_width": null,
 "read_only": 0,
 "read_only_depends_on": null,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "show_dashboard": 0,
 "translatable": 0,
 "unique": 0,
 "width": null
},
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "default": "0",
 "depends_on": null,
 "description": "B2C customer flag. When checked OR tax_id is empty, ZATCA print format renders 'Simplified Tax Invoice' instead of 'Tax Invoice'.",
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Customer",
 "fetch_from": null,
 "fetch_if_empty": 0,
 "fieldname": "custom_is_b2c",
 "fieldtype": "Check",
 "hidden": 0,
 "hide_border": 0,
 "hide_days": 0,
 "hide_seconds": 0,
 "ignore_user_permissions": 0,
 "ignore_xss_filter": 0,
 "in_filter": 1,
 "in_global_search": 0,
 "in_list_view": 0,
 "in_preview": 0,
 "in_standard_filter": 1,
 "insert_after": "customer_type",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Is B2C (Simplified Tax Invoice)",
 "length": 0,
 "mandatory_depends_on": null,
 "modified": "2026-05-06 10:00:00.000000",
 "module": "Rmax Custom",
 "name": "Customer-custom_is_b2c",
 "no_copy": 0,
 "non_negative": 0,
 "options": null,
 "permlevel": 0,
 "precision": "",
 "print_hide": 1,
 "print_hide_if_no_value": 0,
 "print_width": null,
 "read_only": 0,
 "read_only_depends_on": null,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "show_dashboard": 0,
 "translatable": 0,
 "unique": 0,
 "width": null
}
```

- [ ] **Step 2: Validate JSON syntax**

```bash
python3 -c "import json; json.load(open('rmax_custom/fixtures/custom_field.json'))"
```

Expected: no output (valid JSON). Any traceback indicates a stray comma — fix immediately.

- [ ] **Step 3: Apply on dev**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 migrate"
```

Expected: migrate completes; new Custom Field rows visible via `bench --site rmax_dev2 console`:

```python
frappe.db.exists("Custom Field", "Customer-custom_customer_name_ar")
# 'Customer-custom_customer_name_ar'
```

- [ ] **Step 4: Smoke-test field render**

In the dev UI, open any Customer; confirm:
- "Customer Name (Arabic)" Data input appears immediately after `customer_name`
- "Mobile (Arabic)" Data input appears immediately after `mobile_no`
- "Is B2C (Simplified Tax Invoice)" checkbox appears in Customer Type section

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/fixtures/custom_field.json
git commit -m "feat(customer): add Arabic name + mobile + B2C flag custom fields"
```

### Task 1.2: Address Arabic Custom Fields

**Files:**
- Modify: `rmax_custom/fixtures/custom_field.json`

- [ ] **Step 1: Append three Address rows**

Append (same array, before closing `]`):

```json
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "default": null,
 "depends_on": null,
 "description": "Address line 1 in Arabic. Renders RTL on ZATCA print format when populated.",
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Address",
 "fetch_from": null,
 "fetch_if_empty": 0,
 "fieldname": "custom_address_line1_ar",
 "fieldtype": "Data",
 "hidden": 0,
 "hide_border": 0,
 "hide_days": 0,
 "hide_seconds": 0,
 "ignore_user_permissions": 0,
 "ignore_xss_filter": 0,
 "in_filter": 0,
 "in_global_search": 0,
 "in_list_view": 0,
 "in_preview": 0,
 "in_standard_filter": 0,
 "insert_after": "address_line1",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Address Line 1 (Arabic)",
 "length": 0,
 "mandatory_depends_on": null,
 "modified": "2026-05-06 10:00:00.000000",
 "module": "Rmax Custom",
 "name": "Address-custom_address_line1_ar",
 "no_copy": 0,
 "non_negative": 0,
 "options": null,
 "permlevel": 0,
 "precision": "",
 "print_hide": 0,
 "print_hide_if_no_value": 0,
 "print_width": null,
 "read_only": 0,
 "read_only_depends_on": null,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "show_dashboard": 0,
 "translatable": 0,
 "unique": 0,
 "width": null
},
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "default": null,
 "depends_on": null,
 "description": "Address line 2 in Arabic.",
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Address",
 "fetch_from": null,
 "fetch_if_empty": 0,
 "fieldname": "custom_address_line2_ar",
 "fieldtype": "Data",
 "hidden": 0,
 "hide_border": 0,
 "hide_days": 0,
 "hide_seconds": 0,
 "ignore_user_permissions": 0,
 "ignore_xss_filter": 0,
 "in_filter": 0,
 "in_global_search": 0,
 "in_list_view": 0,
 "in_preview": 0,
 "in_standard_filter": 0,
 "insert_after": "address_line2",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Address Line 2 (Arabic)",
 "length": 0,
 "mandatory_depends_on": null,
 "modified": "2026-05-06 10:00:00.000000",
 "module": "Rmax Custom",
 "name": "Address-custom_address_line2_ar",
 "no_copy": 0,
 "non_negative": 0,
 "options": null,
 "permlevel": 0,
 "precision": "",
 "print_hide": 0,
 "print_hide_if_no_value": 0,
 "print_width": null,
 "read_only": 0,
 "read_only_depends_on": null,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "show_dashboard": 0,
 "translatable": 0,
 "unique": 0,
 "width": null
},
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "default": null,
 "depends_on": null,
 "description": "City name in Arabic.",
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Address",
 "fetch_from": null,
 "fetch_if_empty": 0,
 "fieldname": "custom_city_ar",
 "fieldtype": "Data",
 "hidden": 0,
 "hide_border": 0,
 "hide_days": 0,
 "hide_seconds": 0,
 "ignore_user_permissions": 0,
 "ignore_xss_filter": 0,
 "in_filter": 0,
 "in_global_search": 0,
 "in_list_view": 0,
 "in_preview": 0,
 "in_standard_filter": 0,
 "insert_after": "city",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "City (Arabic)",
 "length": 0,
 "mandatory_depends_on": null,
 "modified": "2026-05-06 10:00:00.000000",
 "module": "Rmax Custom",
 "name": "Address-custom_city_ar",
 "no_copy": 0,
 "non_negative": 0,
 "options": null,
 "permlevel": 0,
 "precision": "",
 "print_hide": 0,
 "print_hide_if_no_value": 0,
 "print_width": null,
 "read_only": 0,
 "read_only_depends_on": null,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "show_dashboard": 0,
 "translatable": 0,
 "unique": 0,
 "width": null
}
```

- [ ] **Step 2: Validate JSON**

```bash
python3 -c "import json; json.load(open('rmax_custom/fixtures/custom_field.json'))"
```

Expected: no output.

- [ ] **Step 3: Migrate dev + smoke-test**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 migrate"
```

Open any Address record; confirm three new Arabic fields appear after their English counterparts.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/fixtures/custom_field.json
git commit -m "feat(address): add Arabic line1/line2/city custom fields"
```

### Task 1.3: Delivery Note `custom_consolidated_si` Custom Field

**Files:**
- Modify: `rmax_custom/fixtures/custom_field.json`

- [ ] **Step 1: Append DN row**

```json
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 1,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "default": null,
 "depends_on": null,
 "description": "Set by rmax_custom.api.delivery_note.consolidate_dns_to_si when this DN is consumed in a netted-off Sales Invoice.",
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Delivery Note",
 "fetch_from": null,
 "fetch_if_empty": 0,
 "fieldname": "custom_consolidated_si",
 "fieldtype": "Link",
 "hidden": 0,
 "hide_border": 0,
 "hide_days": 0,
 "hide_seconds": 0,
 "ignore_user_permissions": 1,
 "ignore_xss_filter": 0,
 "in_filter": 0,
 "in_global_search": 0,
 "in_list_view": 0,
 "in_preview": 0,
 "in_standard_filter": 1,
 "insert_after": "custom_inter_company_si",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Consolidated Sales Invoice",
 "length": 0,
 "mandatory_depends_on": null,
 "modified": "2026-05-06 10:00:00.000000",
 "module": "Rmax Custom",
 "name": "Delivery Note-custom_consolidated_si",
 "no_copy": 1,
 "non_negative": 0,
 "options": "Sales Invoice",
 "permlevel": 0,
 "precision": "",
 "print_hide": 1,
 "print_hide_if_no_value": 1,
 "print_width": null,
 "read_only": 1,
 "read_only_depends_on": null,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "show_dashboard": 0,
 "translatable": 0,
 "unique": 0,
 "width": null
}
```

- [ ] **Step 2: Validate JSON + migrate**

```bash
python3 -c "import json; json.load(open('rmax_custom/fixtures/custom_field.json'))"
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 migrate"
```

Expected: no output from JSON check; migrate completes.

- [ ] **Step 3: Verify field exists**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 console <<< 'print(frappe.db.exists(\"Custom Field\", \"Delivery Note-custom_consolidated_si\"))'"
```

Expected: `Delivery Note-custom_consolidated_si`.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/fixtures/custom_field.json
git commit -m "feat(delivery-note): add custom_consolidated_si link field"
```

### Task 1.4: Customer Search-Fields Property Setter Update

**Files:**
- Modify: `rmax_custom/fixtures/property_setter.json` (existing row `Customer-main-search_fields`)

- [ ] **Step 1: Locate and edit the row**

Open `rmax_custom/fixtures/property_setter.json`, find the row with `"name": "Customer-main-search_fields"` (currently around line 411). Change the `value` from:

```
"value": "customer_name,mobile_no,custom_vat_registration_number"
```

to:

```
"value": "customer_name,custom_customer_name_ar,mobile_no,custom_vat_registration_number"
```

Also bump the `modified` timestamp on that row to `"2026-05-06 10:00:00.000000"`.

- [ ] **Step 2: Validate JSON**

```bash
python3 -c "import json; json.load(open('rmax_custom/fixtures/property_setter.json'))"
```

Expected: no output.

- [ ] **Step 3: Apply on dev**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 execute frappe.utils.fixtures.sync_fixtures"
```

Expected: log line `Updating Property Setter Customer-main-search_fields`.

- [ ] **Step 4: Smoke-test Customer search**

In the dev UI, create a test customer with `custom_customer_name_ar = "احمد التجريبي"`. In any Customer Link picker, type `احمد` — confirm the customer appears in the dropdown.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/fixtures/property_setter.json
git commit -m "feat(customer): include custom_customer_name_ar in search_fields"
```

---

## Phase 2 — Print Format (Section A)

### Task 2.1: `get_invoice_title` Helper + Test

**Files:**
- Modify: `rmax_custom/print_helpers.py`
- Create: `rmax_custom/tests/test_print_helpers.py`

- [ ] **Step 1: Write the failing test**

Create `rmax_custom/tests/test_print_helpers.py`:

```python
"""Tests for rmax_custom.print_helpers."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from rmax_custom.print_helpers import get_invoice_title


class TestInvoiceTitleResolution(FrappeTestCase):
    """get_invoice_title returns ('Tax Invoice', 'فاتورة ضريبية') by default and
    flips to the simplified pair when the customer is B2C OR has empty tax_id."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.b2b_name = _ensure_customer(
            "RMAX Test B2B", tax_id="300000000000003", custom_is_b2c=0
        )
        cls.b2c_flag_name = _ensure_customer(
            "RMAX Test B2C Flagged", tax_id="300000000000003", custom_is_b2c=1
        )
        cls.empty_vat_name = _ensure_customer(
            "RMAX Test Empty VAT", tax_id="", custom_is_b2c=0
        )

    def _stub_invoice(self, customer_name):
        return frappe._dict(customer=customer_name)

    def test_b2b_with_vat_returns_tax_invoice(self):
        en, ar = get_invoice_title(self._stub_invoice(self.b2b_name))
        self.assertEqual(en, "Tax Invoice")
        self.assertEqual(ar, "فاتورة ضريبية")

    def test_b2c_flagged_returns_simplified(self):
        en, ar = get_invoice_title(self._stub_invoice(self.b2c_flag_name))
        self.assertEqual(en, "Simplified Tax Invoice")
        self.assertEqual(ar, "فاتورة ضريبية مبسطة")

    def test_empty_vat_returns_simplified(self):
        en, ar = get_invoice_title(self._stub_invoice(self.empty_vat_name))
        self.assertEqual(en, "Simplified Tax Invoice")
        self.assertEqual(ar, "فاتورة ضريبية مبسطة")


def _ensure_customer(name, *, tax_id, custom_is_b2c):
    if frappe.db.exists("Customer", name):
        c = frappe.get_doc("Customer", name)
    else:
        c = frappe.new_doc("Customer")
        c.customer_name = name
        c.customer_group = frappe.db.get_value(
            "Customer Group", {"is_group": 0}, "name"
        ) or "All Customer Groups"
        c.territory = frappe.db.get_value(
            "Territory", {"is_group": 0}, "name"
        ) or "All Territories"
    c.tax_id = tax_id
    c.custom_is_b2c = custom_is_b2c
    c.save(ignore_permissions=True)
    return c.name
```

- [ ] **Step 2: Run test to verify it fails**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 run-tests --app rmax_custom --module rmax_custom.tests.test_print_helpers"
```

Expected: ImportError or AttributeError — `get_invoice_title` not yet defined.

- [ ] **Step 3: Implement `get_invoice_title`**

Append to `rmax_custom/print_helpers.py`:

```python
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
```

If the file does not yet `import frappe`, add it at the top.

- [ ] **Step 4: Run test to verify it passes**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 run-tests --app rmax_custom --module rmax_custom.tests.test_print_helpers"
```

Expected: 3 tests pass, 0 failures.

- [ ] **Step 5: Register Jinja method in hooks.py**

In `rmax_custom/hooks.py`, locate the `jinja = {"methods": [ ... ]}` block. Append (preserving comma discipline):

```python
"rmax_custom.print_helpers.get_invoice_title:get_rmax_invoice_title",
```

- [ ] **Step 6: Verify Jinja registration**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo -u v15 bench --site rmax_dev2 console <<< 'print(frappe.render_template(\"{{ get_rmax_invoice_title({\\\"customer\\\": \\\"RMAX Test B2C Flagged\\\"})[0] }}\", {}))'"
```

Expected: `Simplified Tax Invoice`.

- [ ] **Step 7: Commit**

```bash
git add rmax_custom/print_helpers.py rmax_custom/tests/test_print_helpers.py rmax_custom/hooks.py
git commit -m "feat(print): add get_invoice_title B2C-aware helper + Jinja method"
```

### Task 2.2: Bilingual Customer + Address Print Format Patches

**Files:**
- Modify: `rmax_custom/rmax_custom/print_format/rmax_tax_invoice_zatca/rmax_tax_invoice_zatca.json`

- [ ] **Step 1: Locate the print format `html` field**

The print format JSON stores its template in the `html` field as a single escaped string. Open the file, find `"html":` near the top.

- [ ] **Step 2: Replace the document title block**

Find the existing TAX INVOICE title block (the `<h1>`/`<h2>` rendering "TAX INVOICE - فاتورة ضريبية"). Replace with:

```jinja
{%- set _title = get_rmax_invoice_title(doc) -%}
<table style="width:100%; border:none; margin-bottom:8px;">
  <tr>
    <td style="text-align:left; font-size:14pt; font-weight:bold; border:none;">
      {{ _title[0] }}
    </td>
    <td style="text-align:right; font-size:14pt; font-weight:bold; border:none;" dir="rtl">
      {{ _title[1] }}
    </td>
  </tr>
</table>
```

- [ ] **Step 3: Replace the Customer "Name" cell**

Find the row labelled "Name" / "اسم". Replace the value cell with:

```jinja
{%- set _customer = frappe.get_cached_doc("Customer", doc.customer) -%}
{%- set _ar_name = (_customer.get("custom_customer_name_ar") or "").strip() -%}
{%- set _en_name = (doc.customer_name or _customer.customer_name or "").strip() -%}
{%- if _ar_name and _en_name -%}
  <div>{{ _en_name }}</div>
  <div dir="rtl">{{ _ar_name }}</div>
{%- elif _ar_name -%}
  <div dir="rtl">{{ _ar_name }}</div>
{%- else -%}
  <div>{{ _en_name }}</div>
{%- endif -%}
```

- [ ] **Step 4: Replace the Address cell**

Find the Address row. Replace value cell with:

```jinja
{%- set _addr_name = doc.customer_address or doc.shipping_address_name -%}
{%- if _addr_name -%}
  {%- set _addr = frappe.get_cached_doc("Address", _addr_name) -%}
  {%- set _line1_en = (_addr.address_line1 or "").strip() -%}
  {%- set _line1_ar = (_addr.get("custom_address_line1_ar") or "").strip() -%}
  {%- set _line2_en = (_addr.address_line2 or "").strip() -%}
  {%- set _line2_ar = (_addr.get("custom_address_line2_ar") or "").strip() -%}
  {%- set _city_en = (_addr.city or "").strip() -%}
  {%- set _city_ar = (_addr.get("custom_city_ar") or "").strip() -%}
  {%- if _line1_ar or _line2_ar or _city_ar -%}
    <div>{{ _line1_en }}{% if _line2_en %}, {{ _line2_en }}{% endif %}{% if _city_en %}, {{ _city_en }}{% endif %}</div>
    <div dir="rtl">{{ _line1_ar }}{% if _line2_ar %}، {{ _line2_ar }}{% endif %}{% if _city_ar %}، {{ _city_ar }}{% endif %}</div>
  {%- else -%}
    <div>{{ _line1_en }}{% if _line2_en %}, {{ _line2_en }}{% endif %}{% if _city_en %}, {{ _city_en }}{% endif %}</div>
  {%- endif -%}
{%- endif -%}
```

- [ ] **Step 5: Replace the Phone cell**

```jinja
{%- set _ph_en = (_customer.mobile_no or "").strip() -%}
{%- set _ph_ar = (_customer.get("custom_mobile_ar") or "").strip() -%}
{%- if _ph_ar and _ph_en and _ph_ar != _ph_en -%}
  <div>{{ _ph_en }}</div>
  <div dir="rtl">{{ _ph_ar }}</div>
{%- elif _ph_ar -%}
  <div dir="rtl">{{ _ph_ar }}</div>
{%- else -%}
  <div>{{ _ph_en }}</div>
{%- endif -%}
```

- [ ] **Step 6: Bump `modified` timestamp**

In the same JSON file, update the top-level `"modified"` field to `"2026-05-06 10:00:00.000000"`.

- [ ] **Step 7: Validate JSON**

```bash
python3 -c "import json; json.load(open('rmax_custom/rmax_custom/print_format/rmax_tax_invoice_zatca/rmax_tax_invoice_zatca.json'))"
```

Expected: no output.

- [ ] **Step 8: Reload print format on dev**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 execute frappe.reload_doc --kwargs '{\"module\":\"Rmax Custom\",\"dt\":\"print_format\",\"dn\":\"rmax_tax_invoice_zatca\",\"force\":1}'"
```

Expected: `OK`.

- [ ] **Step 9: Render-test on a B2B and B2C invoice**

Pick one existing B2B SI (customer with `tax_id`) and one B2C SI (no `tax_id` or `custom_is_b2c=1`). Render via:

```
https://rmax-dev.fateherp.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales+Invoice&name=<SI-NAME>&format=RMAX+Tax+Invoice+ZATCA&no_letterhead=0
```

Expected: B2B PDF shows "Tax Invoice / فاتورة ضريبية"; B2C shows "Simplified Tax Invoice / فاتورة ضريبية مبسطة". Customer name renders in EN + AR if both present, fallback to EN-only otherwise. Address and phone follow same fallback rules.

- [ ] **Step 10: Commit**

```bash
git add rmax_custom/rmax_custom/print_format/rmax_tax_invoice_zatca/rmax_tax_invoice_zatca.json
git commit -m "feat(print): bilingual customer/address/phone + simplified-invoice title"
```

### Task 2.3: Drop colons + widen item-code column + fit-on-A4 CSS

**Files:**
- Modify: `rmax_custom/rmax_custom/print_format/rmax_tax_invoice_zatca/rmax_tax_invoice_zatca.json`

- [ ] **Step 1: Strip trailing colons from label cells**

Search the print format `html` for label patterns. Targets: `Invoice Number :`, `Issue Date :`, `Issue Time :`, `Buyer :`, `Name :`, `Address :`, `VAT Number :`, `Phone :`. Strip the trailing ` :` (space + colon) from each label cell — keep the label text only.

Same pass for Arabic labels: strip trailing ` :` after Arabic-script label cells.

- [ ] **Step 2: Inject CSS overrides**

Find the `css` field in the print format JSON. Append (escape backslashes/quotes per JSON rules):

```css
.print-format table.items-table { font-size: 9pt; }
.print-format table.items-table th,
.print-format table.items-table td { padding: 4px 6px; vertical-align: middle; }
.print-format table.items-table th.col-item-code,
.print-format table.items-table td.col-item-code { width: 18%; min-width: 120px; }
.print-format table.items-table thead { display: table-header-group; }
.print-format .totals-block,
.print-format .terms-block,
.print-format .signature-block { page-break-inside: avoid; }
#rmax-page-footer { position: running(footer); text-align: right; font-size: 8pt; }
@page { @bottom-right { content: element(footer); } }
```

If item-table cells don't already carry the `col-item-code` class, add the class to the appropriate `<th>` and item-code-rendering `<td>` in the items table.

- [ ] **Step 3: Add page-footer block**

Inside the `html` field, just before the closing `</body>`-equivalent or at the end of the print body, append:

```html
<div id="rmax-page-footer">
  Page <span class="page"></span> / <span class="topage"></span>
</div>
```

- [ ] **Step 4: Validate JSON**

```bash
python3 -c "import json; json.load(open('rmax_custom/rmax_custom/print_format/rmax_tax_invoice_zatca/rmax_tax_invoice_zatca.json'))"
```

Expected: no output.

- [ ] **Step 5: Reload + render-test 5-row and 7-row invoices**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 execute frappe.reload_doc --kwargs '{\"module\":\"Rmax Custom\",\"dt\":\"print_format\",\"dn\":\"rmax_tax_invoice_zatca\",\"force\":1}'"
```

Manually print one SI with 5 rows; confirm everything fits on a single A4 (header, items, totals, terms, signatures).

Print one SI with 8 rows; confirm pagination — header repeats on page 2, footer renders "Page 1 / 2" then "Page 2 / 2".

- [ ] **Step 6: Commit**

```bash
git add rmax_custom/rmax_custom/print_format/rmax_tax_invoice_zatca/rmax_tax_invoice_zatca.json
git commit -m "feat(print): drop colons, widen item code col, page-of-pages footer"
```

### Task 2.4: Apply identical patches to `rmax_tax_invoice` sibling format (if active)

**Files:**
- Modify: `rmax_custom/rmax_custom/print_format/rmax_tax_invoice/rmax_tax_invoice.json`

- [ ] **Step 1: Confirm format is still in active use**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 console <<< 'print(frappe.db.count(\"Sales Invoice\", filters={\"select_print_heading\": [\"like\", \"%RMAX Tax Invoice%\"]}))'"
```

If the count is 0 AND no operator confirms it's still being chosen from the print picker, **skip this task entirely** — only `rmax_tax_invoice_zatca` is the live target. Document the skip in the commit message of Task 2.3.

If still in use:

- [ ] **Step 2: Repeat Task 2.2 + 2.3 patches against `rmax_tax_invoice.json`**

Apply the same:
- bilingual title block
- bilingual customer/address/phone cells
- colon strip
- CSS + footer block

- [ ] **Step 3: Reload + smoke-test**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 execute frappe.reload_doc --kwargs '{\"module\":\"Rmax Custom\",\"dt\":\"print_format\",\"dn\":\"rmax_tax_invoice\",\"force\":1}'"
```

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/rmax_custom/print_format/rmax_tax_invoice/rmax_tax_invoice.json
git commit -m "feat(print): port bilingual + simplified title to legacy rmax_tax_invoice format"
```

---

## Phase 3 — Branch User SI Tuning (Section B)

### Task 3.1: Hide POS / Debit Note / Payment Date / Taxes section for Branch User

**Files:**
- Modify: `rmax_custom/public/js/sales_invoice_doctype.js`

- [ ] **Step 1: Read existing file to find the right insertion point**

```bash
grep -n "frappe.ui.form.on" rmax_custom/public/js/sales_invoice_doctype.js | head -5
```

Identify the existing top-level `frappe.ui.form.on('Sales Invoice', { ... })` call.

- [ ] **Step 2: Add the hide function and wire into refresh**

At the top of the file (after any module-level constants) add:

```javascript
const _RMAX_SI_HIDE_BYPASS_ROLES = [
    "Sales Manager",
    "System Manager",
    "Sales Master Manager",
    "Accounts Manager",
];

function _rmax_si_branch_user_hide(frm) {
    if (frappe.session.user === "Administrator") return;
    if (_RMAX_SI_HIDE_BYPASS_ROLES.some((r) => frappe.user.has_role(r))) return;
    if (!frappe.user.has_role("Branch User")) return;

    frm.set_df_property("is_pos", "hidden", 1);
    frm.set_df_property("is_debit_note", "hidden", 1);
    frm.set_df_property("payment_due_date", "hidden", 1);

    frm.toggle_display("taxes_section_break", false);
    frm.toggle_display("taxes_and_charges", false);
    frm.toggle_display("taxes", false);
}
```

In the existing `frappe.ui.form.on('Sales Invoice', { refresh(frm) { ... } })` handler, add at the end of the body:

```javascript
_rmax_si_branch_user_hide(frm);
```

If no `refresh` event exists yet, add:

```javascript
frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        _rmax_si_branch_user_hide(frm);
    },
});
```

- [ ] **Step 3: Push and clear cache**

```bash
git add rmax_custom/public/js/sales_invoice_doctype.js
git commit -m "feat(si): hide POS/debit-note/payment-date/taxes for Branch User"
git push origin feature/printables-and-consolidation
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web"
```

- [ ] **Step 4: Manual test as Branch User**

Login as `suhailsudu@gmail.com` (Branch User per CLAUDE.md test-users table). Open New Sales Invoice. Confirm:
- "Include Payment (POS)" checkbox NOT visible
- "Is Rate Adjustment Entry (Debit Note)" checkbox NOT visible
- "Payment Date" / "payment_due_date" field NOT visible
- "Taxes and Charges" section NOT visible (collapsed AND hidden)

Login as Sales Manager (e.g. via System Manager account); open New Sales Invoice. Confirm all three fields and the Taxes section ARE visible.

### Task 3.2: Enable Print for Branch User on Sales Invoice + Delivery Note

**Files:**
- Modify: `rmax_custom/setup.py`

- [ ] **Step 1: Locate `BRANCH_USER_PERMISSIONS` rows**

```bash
grep -n "Sales Invoice\|Delivery Note" rmax_custom/setup.py | head -20
```

Find the `BRANCH_USER_PERMISSIONS = [ ... ]` block; locate the dict rows for `"parent": "Sales Invoice"` and `"parent": "Delivery Note"` with `"role": "Branch User"`.

- [ ] **Step 2: Set `print=1` on both rows**

For each of the two rows, ensure (or add) the key/value pair `"print": 1`. Same for the corresponding `STOCK_USER_EXTRA_PERMISSIONS` rows if Stock User also lacks Print.

- [ ] **Step 3: Run after_migrate on dev**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 execute rmax_custom.setup.after_migrate"
```

Expected: no traceback.

- [ ] **Step 4: Verify Custom DocPerm on dev**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 console <<< 'print(frappe.db.get_value(\"Custom DocPerm\", {\"parent\": \"Sales Invoice\", \"role\": \"Branch User\"}, [\"read\", \"write\", \"create\", \"submit\", \"print\"], as_dict=1))'"
```

Expected: `print` key returns `1`.

- [ ] **Step 5: Manual test**

Login as Branch User; open a submitted Sales Invoice. Confirm a "Print" entry now appears under the Menu / 3-dot dropdown. Click → print dialog opens. Choose `RMAX Tax Invoice ZATCA` → renders the bilingual format.

Repeat for Delivery Note.

- [ ] **Step 6: Commit**

```bash
git add rmax_custom/setup.py
git commit -m "fix(perms): enable Print for Branch User on Sales Invoice + Delivery Note"
```

### Task 3.3: New-customer dialog with Arabic Name field

**Files:**
- Modify: `rmax_custom/public/js/create_customer.js`

- [ ] **Step 1: Read existing dialog field list**

```bash
grep -n "fields" rmax_custom/public/js/create_customer.js | head -20
```

Identify the array of `{fieldname, label, fieldtype, ...}` objects passed to `frappe.prompt` or `frappe.ui.Dialog`.

- [ ] **Step 2: Insert Arabic name field**

Immediately after the `customer_name` entry in the fields array, insert:

```javascript
{
    fieldname: "custom_customer_name_ar",
    label: __("Customer Name (Arabic)"),
    fieldtype: "Data",
    description: __("Optional. Renders on bilingual ZATCA print format and enables Arabic search."),
    reqd: 0,
},
```

- [ ] **Step 3: Map dialog value → Customer doc field on submit**

Find the `frappe.client.insert` or equivalent call inside the dialog's `primary_action`. Pass through the new value:

```javascript
frappe.client.insert({
    doctype: "Customer",
    customer_name: values.customer_name,
    custom_customer_name_ar: values.custom_customer_name_ar || "",
    // ... existing fields preserved
});
```

If the dialog uses `frappe.xcall("rmax_custom.api.customer.create_customer_with_address", ...)`, also pass `custom_customer_name_ar: values.custom_customer_name_ar` and update the server-side helper accordingly.

- [ ] **Step 4: Push and clear cache**

```bash
git add rmax_custom/public/js/create_customer.js
git commit -m "feat(customer): Arabic name field in create-customer dialog"
git push origin feature/printables-and-consolidation
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web"
```

- [ ] **Step 5: Manual test**

Open New Sales Invoice → Customer field → "+ Create New Customer" link. Confirm dialog now shows "Customer Name (Arabic)" field below "Customer Name". Type both, save. Open the new Customer record → confirm `custom_customer_name_ar` populated.

### Task 3.4: Update server-side `create_customer_with_address` to accept `custom_customer_name_ar`

**Files:**
- Modify: `rmax_custom/api/customer.py`

- [ ] **Step 1: Locate function signature**

```bash
grep -n "def create_customer_with_address" rmax_custom/api/customer.py
```

- [ ] **Step 2: Add the parameter and forward it**

Add `custom_customer_name_ar: str = ""` to the kwargs. Inside the function body, after creating the Customer doc, set:

```python
if custom_customer_name_ar:
    customer.custom_customer_name_ar = custom_customer_name_ar
```

before the `customer.insert(...)` call.

- [ ] **Step 3: Test via console**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 console <<< 'from rmax_custom.api.customer import create_customer_with_address; r = create_customer_with_address(customer_name=\"RMAX Plan Test AR\", customer_group=\"Commercial\", territory=\"Saudi Arabia\", custom_customer_name_ar=\"تجريبي\"); print(r); print(frappe.db.get_value(\"Customer\", r, \"custom_customer_name_ar\"))'"
```

Expected: prints the new customer name and `تجريبي`.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/api/customer.py
git commit -m "feat(customer): create_customer_with_address accepts custom_customer_name_ar"
```

---

## Phase 4 — DN + Return Consolidation (Section C)

### Task 4.1: Refactor `inter_company_dn` — extract `_build_inter_company_si_from_buckets`

**Files:**
- Modify: `rmax_custom/inter_company_dn.py`

- [ ] **Step 1: Read existing builder**

Open `rmax_custom/inter_company_dn.py`. Find the inner-loop in `create_si_from_multiple_dns` that walks `dns` and appends to `si.items`.

- [ ] **Step 2: Extract bucket-aware helper**

Add a new private function (above `create_si_from_multiple_dns`):

```python
def _build_inter_company_si_from_buckets(dns, buckets):
    """Build an inter-company Draft Sales Invoice from pre-netted buckets.

    Used by both the all-positive path (``create_si_from_multiple_dns``) and
    the new mixed-net path (``api.delivery_note.consolidate_dns_to_si``).
    """
    head = dns[0]
    si = frappe.new_doc("Sales Invoice")
    si.customer = head.customer
    si.customer_name = head.customer_name
    si.company = head.represents_company  # selling-side company for inter-company
    si.currency = head.currency
    si.posting_date = frappe.utils.today()
    si.set_posting_time = 1
    si.update_stock = 0  # DNs already moved stock

    branch = head.get("custom_inter_company_branch")
    if branch:
        si.custom_inter_company_branch = branch
        # Pull set_warehouse + cost_center from the Inter Company Branch row
        # for the SELLING side.
        icb = frappe.get_cached_doc("Inter Company Branch", branch)
        si.set_warehouse = icb.warehouse
        si.cost_center = icb.cost_center

    if head.taxes_and_charges:
        si.taxes_and_charges = head.taxes_and_charges
        for t in head.taxes:
            si.append("taxes", _copy_tax_row(t))

    for (item_code, uom), b in buckets.items():
        if b["qty"] <= 0:
            continue
        rate = (b["amount"] / b["qty"]) if b["qty"] else 0
        src = b["src_rows"][0]
        si.append("items", {
            "item_code": item_code,
            "qty": b["qty"],
            "uom": uom,
            "rate": rate,
            "delivery_note": src["dn"],
            "dn_detail": src["row"],
        })

    return si


def _copy_tax_row(t):
    return {
        "charge_type": t.charge_type,
        "account_head": t.account_head,
        "rate": t.rate,
        "description": t.description,
        "cost_center": t.cost_center,
        "included_in_print_rate": t.included_in_print_rate,
    }
```

- [ ] **Step 3: Refactor `create_si_from_multiple_dns` to use buckets**

Replace its item-building inner loop with a call to a new helper that builds buckets with sign=+1 for every row (positive-only), then calls `_build_inter_company_si_from_buckets`:

```python
def _build_positive_only_buckets(dns):
    buckets = {}
    for dn in dns:
        for row in dn.items:
            key = (row.item_code, row.uom)
            b = buckets.setdefault(key, {
                "qty": 0, "amount": 0, "uom": row.uom, "src_rows": [],
            })
            b["qty"] += abs(row.qty or 0)
            b["amount"] += abs(row.amount or (row.qty * row.rate) or 0)
            b["src_rows"].append({"dn": dn.name, "row": row.name})
    return buckets
```

In `create_si_from_multiple_dns`, after validation, replace the manual SI construction with:

```python
buckets = _build_positive_only_buckets(dns)
si = _build_inter_company_si_from_buckets(dns, buckets)
si.insert(ignore_permissions=False)
# ... existing DN-stamp + return logic preserved
```

- [ ] **Step 4: Run existing test for inter-company SI consolidation**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 run-tests --app rmax_custom --module rmax_custom.rmax_custom.doctype.inter_company_branch.test_inter_company_branch"
```

Expected: existing tests pass.

If a regression occurs, the refactor changed semantics. Likely causes: tax row copy no longer covers a property the original had; `cost_center` resolution path differs. Compare against snapshot.

- [ ] **Step 5: Manual smoke-test**

In the dev UI, select 2 inter-company DNs from the list view → "Create Inter-Company Sales Invoice" → confirm the Draft SI builds with the same item rows as before this refactor.

- [ ] **Step 6: Commit**

```bash
git add rmax_custom/inter_company_dn.py
git commit -m "refactor(inter-company): extract _build_inter_company_si_from_buckets helper"
```

### Task 4.2: Write `consolidate_dns_to_si` test (TDD)

**Files:**
- Create: `rmax_custom/tests/test_dn_consolidation.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for rmax_custom.api.delivery_note.consolidate_dns_to_si — mixed
DN + Return DN net-off consolidation path."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from rmax_custom.api.delivery_note import consolidate_dns_to_si


class TestConsolidateDnsToSi(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = _ensure_customer("RMAX Consol Test")
        cls.item = _ensure_item("RMAX-CONSOL-TEST-ITEM")
        cls.company = _pick_default_company()
        cls.warehouse = _pick_default_warehouse(cls.company)

    def test_mixed_batch_nets_off(self):
        dn1 = _make_submitted_dn(self.customer, self.item, self.company,
                                 self.warehouse, qty=100, rate=10)
        dn2 = _make_submitted_dn(self.customer, self.item, self.company,
                                 self.warehouse, qty=50, rate=10)
        dn3 = _make_submitted_dn(self.customer, self.item, self.company,
                                 self.warehouse, qty=30, rate=10)
        ret = _make_submitted_return_dn(dn1, qty=40)

        si_name = consolidate_dns_to_si([dn1.name, dn2.name, dn3.name, ret.name])

        si = frappe.get_doc("Sales Invoice", si_name)
        self.assertEqual(si.docstatus, 0)
        self.assertEqual(si.customer, self.customer)
        self.assertEqual(si.update_stock, 0)
        # net = 100 + 50 + 30 - 40 = 140
        total_qty = sum(flt(r.qty) for r in si.items if r.item_code == self.item)
        self.assertEqual(total_qty, 140)

    def test_all_positive_batch_works_like_classic_consolidation(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=10, rate=10)
        si_name = consolidate_dns_to_si([dn.name])
        si = frappe.get_doc("Sales Invoice", si_name)
        self.assertEqual(flt(si.items[0].qty), 10)

    def test_mismatched_customer_throws(self):
        c1 = _ensure_customer("RMAX Consol Cust A")
        c2 = _ensure_customer("RMAX Consol Cust B")
        dn_a = _make_submitted_dn(c1, self.item, self.company,
                                  self.warehouse, qty=5, rate=10)
        dn_b = _make_submitted_dn(c2, self.item, self.company,
                                  self.warehouse, qty=5, rate=10)
        with self.assertRaises(frappe.ValidationError):
            consolidate_dns_to_si([dn_a.name, dn_b.name])

    def test_empty_input_throws(self):
        with self.assertRaises(frappe.ValidationError):
            consolidate_dns_to_si([])

    def test_already_consolidated_dn_throws(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=5, rate=10)
        consolidate_dns_to_si([dn.name])
        with self.assertRaises(frappe.ValidationError):
            consolidate_dns_to_si([dn.name])

    def test_si_cancel_clears_stamp(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=5, rate=10)
        si_name = consolidate_dns_to_si([dn.name])
        si = frappe.get_doc("Sales Invoice", si_name)
        si.submit()
        si.cancel()
        self.assertFalse(
            frappe.db.get_value("Delivery Note", dn.name, "custom_consolidated_si")
        )


# --- fixtures helpers ---

def _ensure_customer(name):
    if frappe.db.exists("Customer", name):
        return name
    c = frappe.new_doc("Customer")
    c.customer_name = name
    c.customer_group = frappe.db.get_value(
        "Customer Group", {"is_group": 0}, "name"
    ) or "All Customer Groups"
    c.territory = frappe.db.get_value(
        "Territory", {"is_group": 0}, "name"
    ) or "All Territories"
    c.save(ignore_permissions=True)
    return c.name


def _ensure_item(item_code):
    if frappe.db.exists("Item", item_code):
        return item_code
    i = frappe.new_doc("Item")
    i.item_code = item_code
    i.item_name = item_code
    i.item_group = frappe.db.get_value(
        "Item Group", {"is_group": 0}, "name"
    ) or "All Item Groups"
    i.stock_uom = "Nos"
    i.is_stock_item = 0  # avoid bin/valuation setup in unit tests
    i.save(ignore_permissions=True)
    return i.name


def _pick_default_company():
    return frappe.db.get_single_value("Global Defaults", "default_company") \
        or frappe.db.get_value("Company", {}, "name")


def _pick_default_warehouse(company):
    return frappe.db.get_value(
        "Warehouse", {"company": company, "is_group": 0}, "name"
    )


def _make_submitted_dn(customer, item, company, warehouse, *, qty, rate):
    dn = frappe.new_doc("Delivery Note")
    dn.customer = customer
    dn.company = company
    dn.set_warehouse = warehouse
    dn.append("items", {
        "item_code": item,
        "qty": qty,
        "rate": rate,
        "warehouse": warehouse,
        "uom": "Nos",
    })
    dn.insert(ignore_permissions=True)
    dn.submit()
    return dn


def _make_submitted_return_dn(parent_dn, *, qty):
    ret = frappe.new_doc("Delivery Note")
    ret.customer = parent_dn.customer
    ret.company = parent_dn.company
    ret.set_warehouse = parent_dn.set_warehouse
    ret.is_return = 1
    ret.return_against = parent_dn.name
    src_row = parent_dn.items[0]
    ret.append("items", {
        "item_code": src_row.item_code,
        "qty": -1 * abs(qty),
        "rate": src_row.rate,
        "warehouse": src_row.warehouse,
        "uom": src_row.uom,
        "delivery_note": parent_dn.name,
        "dn_detail": src_row.name,
    })
    ret.insert(ignore_permissions=True)
    ret.submit()
    return ret
```

- [ ] **Step 2: Run test — confirm failure**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 run-tests --app rmax_custom --module rmax_custom.tests.test_dn_consolidation"
```

Expected: ImportError — `consolidate_dns_to_si` not yet defined.

- [ ] **Step 3: Commit failing test**

```bash
git add rmax_custom/tests/test_dn_consolidation.py
git commit -m "test(consolidation): TDD failing tests for consolidate_dns_to_si"
```

### Task 4.3: Implement `consolidate_dns_to_si`

**Files:**
- Modify: `rmax_custom/api/delivery_note.py`

- [ ] **Step 1: Add imports**

At the top of the file (after existing imports), add:

```python
from rmax_custom.inter_company_dn import (
    _build_inter_company_si_from_buckets,
    _copy_tax_row,
)
```

- [ ] **Step 2: Add helpers**

After `create_return_si_from_multiple_dns`, append:

```python
def _normalise_names(delivery_note_names):
    if isinstance(delivery_note_names, str):
        delivery_note_names = json.loads(delivery_note_names)
    if not delivery_note_names:
        frappe.throw(_("Select at least one Delivery Note"))
    return delivery_note_names


def _validate_consolidation_batch(dns):
    if any(d.docstatus != 1 for d in dns):
        frappe.throw(_("All Delivery Notes must be submitted"))

    for d in dns:
        existing = d.get("custom_consolidated_si")
        if existing and frappe.db.exists(
            "Sales Invoice", {"name": existing, "docstatus": ["!=", 2]}
        ):
            frappe.throw(_(
                "DN {0} already linked to non-cancelled Sales Invoice {1}"
            ).format(d.name, existing))

    keys = ["customer", "company", "currency"]
    first = {k: dns[0].get(k) for k in keys}
    for d in dns[1:]:
        for k in keys:
            if d.get(k) != first[k]:
                frappe.throw(_(
                    "DN {0} mismatched on {1}: expected {2}, got {3}"
                ).format(d.name, k, first[k], d.get(k)))


def _net_items_across_dns(dns):
    """Bucket rows by (item_code, uom). Return DNs subtract."""
    buckets = {}
    for dn in dns:
        sign = -1 if dn.is_return else 1
        for row in dn.items:
            key = (row.item_code, row.uom)
            b = buckets.setdefault(key, {
                "qty": 0, "amount": 0, "uom": row.uom, "src_rows": [],
            })
            qty = sign * abs(flt(row.qty or 0))
            amount = sign * abs(flt(row.amount or (row.qty * row.rate) or 0))
            b["qty"] += qty
            b["amount"] += amount
            b["src_rows"].append({"dn": dn.name, "row": row.name})
    return buckets


def _build_consolidated_standard_si(dns, buckets):
    head = dns[0]
    si = frappe.new_doc("Sales Invoice")
    si.customer = head.customer
    si.customer_name = head.customer_name
    si.company = head.company
    si.currency = head.currency
    si.posting_date = frappe.utils.today()
    si.set_posting_time = 1
    si.update_stock = 0
    if head.set_warehouse:
        si.set_warehouse = head.set_warehouse
    if head.get("branch"):
        si.branch = head.get("branch")

    # Inherit taxes from first non-return DN.
    for dn in dns:
        if not dn.is_return and dn.taxes_and_charges:
            si.taxes_and_charges = dn.taxes_and_charges
            for t in dn.taxes:
                si.append("taxes", _copy_tax_row(t))
            break

    for (item_code, uom), b in buckets.items():
        if b["qty"] <= 0:
            continue
        rate = (b["amount"] / b["qty"]) if b["qty"] else 0
        src = b["src_rows"][0]
        si.append("items", {
            "item_code": item_code,
            "qty": b["qty"],
            "uom": uom,
            "rate": rate,
            "delivery_note": src["dn"],
            "dn_detail": src["row"],
        })

    return si


@frappe.whitelist()
def consolidate_dns_to_si(delivery_note_names):
    """Mixed DN + Return DN consolidation into a single Draft Sales Invoice
    with net-off by (item_code, uom)."""
    names = _normalise_names(delivery_note_names)
    dns = [frappe.get_doc("Delivery Note", n) for n in names]

    _validate_consolidation_batch(dns)
    buckets = _net_items_across_dns(dns)

    is_inter_company = bool(dns[0].get("custom_is_inter_company"))
    if is_inter_company:
        # All rows must agree.
        if any(not d.get("custom_is_inter_company") for d in dns):
            frappe.throw(_("Cannot mix inter-company and standard DNs in one batch"))
        si = _build_inter_company_si_from_buckets(dns, buckets)
    else:
        si = _build_consolidated_standard_si(dns, buckets)

    if not si.items:
        frappe.throw(_(
            "After netting returns, no item has positive qty. "
            "Sales Invoice not created."
        ))

    si.insert(ignore_permissions=False)

    for dn in dns:
        frappe.db.set_value(
            "Delivery Note", dn.name,
            "custom_consolidated_si", si.name,
            update_modified=False,
        )

    return si.name
```

- [ ] **Step 3: Run tests — confirm pass**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 run-tests --app rmax_custom --module rmax_custom.tests.test_dn_consolidation"
```

Expected: 6 tests pass.

If `test_si_cancel_clears_stamp` fails, the cancel hook isn't wired yet — proceed to Task 4.4 and re-run.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/api/delivery_note.py
git commit -m "feat(consolidation): consolidate_dns_to_si — mixed DN+Return net-off API"
```

### Task 4.4: SI on_cancel — clear `custom_consolidated_si` on linked DNs

**Files:**
- Modify: `rmax_custom/inter_company_dn.py`

- [ ] **Step 1: Locate `sales_invoice_on_cancel`**

```bash
grep -n "def sales_invoice_on_cancel" rmax_custom/inter_company_dn.py
```

- [ ] **Step 2: Extend the function**

After the existing inter-company stamp clear logic, append:

```python
    # Clear the net-off consolidation stamp on every DN linked via
    # custom_consolidated_si. (Set by api.delivery_note.consolidate_dns_to_si.)
    consolidated_dns = frappe.get_all(
        "Delivery Note",
        filters={"custom_consolidated_si": doc.name},
        pluck="name",
    )
    for dn_name in consolidated_dns:
        frappe.db.set_value(
            "Delivery Note", dn_name,
            "custom_consolidated_si", None,
            update_modified=False,
        )
```

- [ ] **Step 3: Re-run consolidation tests**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 run-tests --app rmax_custom --module rmax_custom.tests.test_dn_consolidation::TestConsolidateDnsToSi::test_si_cancel_clears_stamp"
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/inter_company_dn.py
git commit -m "fix(consolidation): SI cancel clears DN.custom_consolidated_si stamp"
```

### Task 4.5: Add list-view menu action

**Files:**
- Modify: `rmax_custom/public/js/delivery_note_list.js`

- [ ] **Step 1: Add the menu wiring**

In the `onload(listview)` handler, after the two existing `add_actions_menu_item` calls, append:

```javascript
listview.page.add_actions_menu_item(
    __("Consolidate to Sales Invoice (Net Returns)"),
    function () {
        _rmax_consolidate_dns(listview);
    }
);
```

At the bottom of the file, add the helper:

```javascript
function _rmax_consolidate_dns(listview) {
    const selected = listview.get_checked_items().map((row) => row.name);
    if (!selected.length) {
        frappe.msgprint(__("Select at least one Delivery Note first."));
        return;
    }

    frappe.confirm(
        __(
            "Consolidate {0} Delivery Note(s) into one Draft Sales Invoice with returns netted off?",
            [selected.length]
        ),
        function () {
            frappe.call({
                method: "rmax_custom.api.delivery_note.consolidate_dns_to_si",
                args: {
                    delivery_note_names: selected,
                },
                freeze: true,
                freeze_message: __("Building Sales Invoice..."),
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("Created {0}", [r.message]),
                            indicator: "green",
                        });
                        frappe.set_route("Form", "Sales Invoice", r.message);
                    }
                },
            });
        }
    );
}
```

- [ ] **Step 2: Push + clear cache**

```bash
git add rmax_custom/public/js/delivery_note_list.js
git commit -m "feat(consolidation): list-view 'Consolidate to SI (Net Returns)' menu item"
git push origin feature/printables-and-consolidation
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web"
```

- [ ] **Step 3: Manual end-to-end test**

In the dev UI (login as `shameel@rmax.com` Branch User), DN list view:
1. Create 2 DNs (qty 50, qty 30) for the same customer
2. Create a Return DN (qty 20) against DN-1
3. Tick all 3 in the list, Actions → "Consolidate to Sales Invoice (Net Returns)"
4. Confirm → routed to a new Draft SI
5. Verify SI has one row with qty=60 (50+30-20)
6. Verify each DN's `custom_consolidated_si` field shows the new SI name
7. Submit the SI, then cancel it. Verify `custom_consolidated_si` clears on all 3 DNs.

---

## Phase 5 — DN Source Warehouse Auto-set (Section D1)

### Task 5.1: Server-side `set_warehouse_from_branch` for Delivery Note

**Files:**
- Modify: `rmax_custom/branch_defaults.py`
- Modify: `rmax_custom/hooks.py`

- [ ] **Step 1: Verify `set_warehouse_from_branch` already exists**

```bash
grep -n "def set_warehouse_from_branch" rmax_custom/branch_defaults.py
```

If it exists and already sets `set_warehouse`, jump to Step 3. If not, add it:

```python
def set_warehouse_from_branch(doc, method=None):
    """Auto-fill ``set_warehouse`` from the user's Branch Configuration default
    when the field is empty on insert. Honoured for Branch User; bypass roles
    skip the auto-fill."""
    if doc.get("set_warehouse"):
        return
    bypass = {"Sales Manager", "System Manager", "Sales Master Manager",
              "Stock Manager", "Administrator"}
    user_roles = set(frappe.get_roles(frappe.session.user))
    if user_roles & bypass:
        return

    branch_warehouses = _get_user_branch_warehouses(frappe.session.user)
    if branch_warehouses:
        doc.set_warehouse = branch_warehouses[0]


def _get_user_branch_warehouses(user):
    rows = frappe.get_all(
        "Branch Configuration User",
        filters={"user": user},
        pluck="parent",
    )
    if not rows:
        return []
    return frappe.get_all(
        "Branch Configuration Warehouse",
        filters={"parent": ("in", rows)},
        pluck="warehouse",
    )
```

- [ ] **Step 2: Register hook**

In `rmax_custom/hooks.py`, find the `doc_events` block. Locate the `"Delivery Note"` key. Add (or extend the existing `before_insert` list):

```python
"Delivery Note": {
    "before_insert": [
        # ... existing entries preserved
        "rmax_custom.branch_defaults.set_warehouse_from_branch",
    ],
    # ... rest of existing entries preserved
},
```

If `before_insert` was previously a single string, convert to a list with both entries.

- [ ] **Step 3: Manual test via REST**

```bash
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 console <<< 'frappe.set_user(\"shameel@rmax.com\"); dn = frappe.new_doc(\"Delivery Note\"); dn.customer = frappe.db.get_value(\"Customer\", {}, \"name\"); dn.company = frappe.db.get_value(\"Company\", {}, \"name\"); dn.append(\"items\", {\"item_code\": frappe.db.get_value(\"Item\", {\"is_stock_item\": 0}, \"name\"), \"qty\": 1, \"rate\": 10, \"uom\": \"Nos\"}); dn.insert(ignore_permissions=False); print(\"set_warehouse=\", dn.set_warehouse)'"
```

Expected: prints non-empty warehouse name from shameel's branch config.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/branch_defaults.py rmax_custom/hooks.py
git commit -m "feat(dn): auto-fill set_warehouse from branch config on insert"
```

### Task 5.2: Client-side DN form auto-fill on `refresh`

**Files:**
- Modify: `rmax_custom/public/js/delivery_note_doctype.js`

- [ ] **Step 1: Add the auto-fill block**

If the file doesn't have a `frappe.ui.form.on('Delivery Note', { ... })` block, add one at the bottom. Otherwise extend the existing `refresh` handler:

```javascript
frappe.ui.form.on("Delivery Note", {
    refresh(frm) {
        _rmax_dn_autofill_source_warehouse(frm);
    },
});

function _rmax_dn_autofill_source_warehouse(frm) {
    if (!frm.is_new()) return;
    if (frm.doc.set_warehouse) return;

    const bypass = ["Sales Manager","System Manager","Sales Master Manager",
                    "Stock Manager"];
    if (frappe.session.user === "Administrator") return;
    if (bypass.some((r) => frappe.user.has_role(r))) return;

    frappe.call({
        method: "rmax_custom.branch_defaults.get_user_branch_warehouses",
        callback(r) {
            if (r.message && r.message.length && !frm.doc.set_warehouse) {
                frm.set_value("set_warehouse", r.message[0]);
            }
        },
    });
}
```

- [ ] **Step 2: Add the whitelisted helper if missing**

In `rmax_custom/branch_defaults.py`:

```bash
grep -n "def get_user_branch_warehouses" rmax_custom/branch_defaults.py
```

If absent, add:

```python
@frappe.whitelist()
def get_user_branch_warehouses():
    """Return the list of warehouse names mapped to the current user via
    Branch Configuration User → Branch Configuration Warehouse rows.

    Order: as configured in the Branch Configuration child table; first row
    is the user's default."""
    return _get_user_branch_warehouses(frappe.session.user)
```

- [ ] **Step 3: Push + clear cache**

```bash
git add rmax_custom/public/js/delivery_note_doctype.js rmax_custom/branch_defaults.py
git commit -m "feat(dn): client auto-fill set_warehouse on form refresh"
git push origin feature/printables-and-consolidation
ssh root@5.189.131.148 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull origin feature/printables-and-consolidation && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web"
```

- [ ] **Step 4: Manual test**

Login as Branch User; New Delivery Note. Confirm `Source Warehouse` field pre-fills with the user's branch default warehouse the moment the form loads (no manual click required).

Login as Stock Manager; New Delivery Note. Confirm `Source Warehouse` is left blank (bypass role skips auto-fill).

---

## Phase 6 — Deploy + Verify

### Task 6.1: Deploy to UAT

- [ ] **Step 1: Push final branch + open PR or fast-forward main**

```bash
git push origin feature/printables-and-consolidation
git checkout main
git merge --no-ff feature/printables-and-consolidation -m "merge: printables + branch user SI tuning + DN consolidation"
git push origin main
```

- [ ] **Step 2: UAT git pull + fixture sync + setup**

```bash
ssh root@185.193.19.184 "cd /home/v15/frappe-bench && sudo -u v15 git -C apps/rmax_custom pull upstream main && sudo -u v15 bench --site rmax-uat2.enfonoerp.com execute frappe.utils.fixtures.sync_fixtures && sudo -u v15 bench --site rmax-uat2.enfonoerp.com execute rmax_custom.setup.after_migrate && sudo -u v15 bench --site rmax-uat2.enfonoerp.com clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web"
```

Expected: each step exits 0, no traceback.

- [ ] **Step 3: UAT smoke (login as a Branch User)**

Verify:
- Customer master shows new AR fields
- New SI form hides POS/Debit Note/Payment Date/Taxes for Branch User
- New DN form auto-fills source warehouse
- DN list shows 3rd menu item "Consolidate to Sales Invoice (Net Returns)"
- Existing SI prints with bilingual title (B2C → Simplified Tax Invoice)

### Task 6.2: Deploy to PROD

- [ ] **Step 1: PROD git pull + migrate**

```bash
ssh root@161.97.130.108 "cd /home/frappe/frappe-bench && sudo -u frappe git -C apps/rmax_custom pull upstream main && sudo -u frappe bench --site rmax.enfonoerp.com migrate && sudo -u frappe bench --site rmax.enfonoerp.com clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web"
```

Expected: migrate completes, no traceback.

- [ ] **Step 2: PROD smoke (System Manager + Branch User)**

Run the same checks as Task 6.1 Step 3 against `https://rmax.enfonoerp.com`.

- [ ] **Step 3: Notify client**

Send change-log message: features delivered (A.1–A.5, B.1–B.5, C.1–C.3, D1) plus the deferred D2 audit ask for specific failing tiles.

---

## Acceptance Criteria

- [ ] **AC-A1:** B2C customer (`tax_id` empty OR `custom_is_b2c=1`) prints with title "Simplified Tax Invoice / فاتورة ضريبية مبسطة"; B2B customer prints with "Tax Invoice / فاتورة ضريبية"
- [ ] **AC-A2:** Pagination "Page 1 / 2", "Page 2 / 2" renders correctly on a 7+ row invoice
- [ ] **AC-A3:** No trailing colons after labels in print format
- [ ] **AC-A4:** 5–6 item invoice fits on a single A4 with footer + terms
- [ ] **AC-A5:** Customer Arabic name renders in EN+AR if both populated; AR-only or EN-only fallback works
- [ ] **AC-B1:** Branch User sees no "Include Payment (POS)", "Is Rate Adjustment Entry", "Payment Date" fields on Sales Invoice
- [ ] **AC-B2:** Branch User sees no "Taxes and Charges" section on Sales Invoice
- [ ] **AC-B3:** Branch User has Print menu item working on Sales Invoice + Delivery Note
- [ ] **AC-B4:** New customer dialog has Arabic name field
- [ ] **AC-B5:** Customer Link picker matches Arabic-name input
- [ ] **AC-C1:** Mixed DN + Return DN batch consolidates to single Draft SI with net-off
- [ ] **AC-C2:** Consolidated SI cancel clears DN's `custom_consolidated_si`
- [ ] **AC-C3:** Inter-company DNs route through inter-company path (PI auto-creates on buying side)
- [ ] **AC-D1:** New DN as Branch User auto-fills source warehouse from branch config
- [ ] **AC-D2:** (Deferred) Stock User dashboard permission audit completes — separate follow-up

---

## Self-Review Checklist (Plan Author)

Filled by plan author before handing off:

- [x] Spec coverage: every section A.1–A.6, B.1–B.5, C.1–C.7, D1 maps to a task
- [x] Placeholder scan: no TBD/TODO/"add error handling"; all code blocks complete
- [x] Type consistency: `_build_inter_company_si_from_buckets`, `_copy_tax_row`, `_normalise_names`, `_validate_consolidation_batch`, `_net_items_across_dns`, `_build_consolidated_standard_si`, `consolidate_dns_to_si`, `get_invoice_title`, `_rmax_si_branch_user_hide`, `_rmax_dn_autofill_source_warehouse`, `set_warehouse_from_branch`, `get_user_branch_warehouses` — names consistent across tasks
- [x] D2 explicitly deferred with audit framework documented in spec; not blocking ship
