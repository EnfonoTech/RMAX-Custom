# Printables, Branch User SI Tuning, DN+Return Consolidation — Design

**Date:** 2026-05-06
**Status:** Draft
**Source:** Client docx `Printables Status Branch Address and Mobile Number.docx` (extracted to `/tmp/docx_printables/`)
**Images referenced:**
- IMG-1: `/tmp/docx_printables/media/image.jpg` — hand-marked Tax Invoice mockup (10 MB)
- IMG-2: `/tmp/docx_printables/media/image2.jpg` — Sales Invoice header with X-marks on POS/Debit Note/Payment Date
- IMG-3: `/tmp/docx_printables/media/image3.jpg` — Sales Invoice Taxes & Charges section circled

---

## 1. Scope

| Section | Topic |
|---------|-------|
| A | Tax Invoice / Simplified Tax Invoice print format rework (5 sub-items) |
| B | Sales Invoice form tuning for Branch User (5 sub-items) |
| C | Mixed DN + Return DN consolidation into a single Sales Invoice |
| D1 | Delivery Note `set_warehouse` auto-fill on form load |
| D2 | Stock User dashboard permission audit (deferred, see §7) |

## 2. Out of Scope

- Stock User permission audit beyond enumeration framework (§D2)
- POS layout / popup changes
- ZATCA Phase 2 e-invoice payload changes (existing integration unchanged)
- Anything not directly listed in the docx

---

## 3. Section A — Print Format

### A.1 Bilingual customer block

Render Arabic block when Customer master has Arabic name; fall back to English; render both stacked when both present.

**New Custom Fields**

| DocType | Fieldname | Type | Notes |
|---------|-----------|------|-------|
| Customer | `custom_customer_name_ar` | Data | Inserted in customer_details section |
| Customer | `custom_mobile_ar` | Data | Inserted in contact_html block |
| Customer | `custom_is_b2c` | Check | B2B/B2C manual override |
| Address | `custom_address_line1_ar` | Data | Mirrors `address_line1` |
| Address | `custom_address_line2_ar` | Data | Mirrors `address_line2` |
| Address | `custom_city_ar` | Data | Mirrors `city` |

**Render logic in print format Jinja:**

```jinja
{%- set ar_name = (customer.custom_customer_name_ar or '').strip() -%}
{%- set en_name = (customer.customer_name or '').strip() -%}
{%- if ar_name and en_name -%}
  <span class="en">{{ en_name }}</span><br>
  <span class="ar" dir="rtl">{{ ar_name }}</span>
{%- elif ar_name -%}
  <span dir="rtl">{{ ar_name }}</span>
{%- else -%}
  {{ en_name }}
{%- endif -%}
```

Same pattern for address (resolved via existing helper `get_rmax_company_address` adapted to customer billing address) and mobile (`get_rmax_customer_phone` extended for AR variant).

### A.2 Pagination "Page X of Y"

wkhtmltopdf substitutes `<span class="page">` with the current page number and `<span class="topage">` with the total page count when rendered as page footer. Implementation:

- Add hidden footer block in print format HTML:
  ```html
  <div id="rmax-page-footer">
    Page <span class="page"></span> / <span class="topage"></span>
  </div>
  ```
- CSS positions it at bottom margin so it appears on every page
- Confirm via test print on a 7-row invoice (forces 2 pages)

### A.3 Drop colons after labels

Audit print format Jinja and remove trailing `:` after label cells (Invoice Number, Issue Date, Issue Time, Buyer, Address, VAT Number, Phone). Values render in adjacent grid cell — colon is redundant.

### A.4 Item table layout — fit 5–6 items + footer + terms on 1 A4

- Item code column: `min-width 120px`, `width 18%`
- Row vertical padding: `4px` (was 8px)
- Body font-size: `9pt` if 6 rows still overflow at 10pt
- Stickiness: footer (Total Amounts block + Terms block + signature row) glued to bottom of last page
- Header row repeats on overflow page via CSS `display: table-header-group`

### A.5 B2C → "Simplified Tax Invoice"

**New helper** in `rmax_custom/print_helpers.py`:

```python
def get_invoice_title(doc):
    """Return (en_title, ar_title) tuple based on customer B2C status."""
    customer = frappe.get_cached_doc("Customer", doc.customer)
    is_b2c = bool(customer.get("custom_is_b2c")) or not (customer.get("tax_id") or "").strip()
    if is_b2c:
        return ("Simplified Tax Invoice", "فاتورة ضريبية مبسطة")
    return ("Tax Invoice", "فاتورة ضريبية")
```

**Registration** in `hooks.py::jinja.methods`:

```python
"rmax_custom.print_helpers.get_invoice_title:get_rmax_invoice_title",
```

**Print format header** uses `get_rmax_invoice_title(doc)` to render bilingual title.

### A.6 Migration

- Custom Fields shipped via `fixtures/custom_field.json`; included in fixture filter list in `hooks.py`
- Property Setter `Customer.search_fields` = `customer_name,custom_customer_name_ar,customer_id,tax_id` (used by §B.4 too)
- Deploy: `bench migrate` (DEV/PROD), `bench execute frappe.utils.fixtures.sync_fixtures` (UAT — migrate blocked)

---

## 4. Section B — Sales Invoice Tuning for Branch User

### B.1 Hide form fields (IMG-2 / IMG-3)

Extend `public/js/sales_invoice_doctype.js`:

```js
function rmax_branch_user_hide(frm) {
    const bypass = ['Sales Manager','System Manager','Sales Master Manager','Accounts Manager'];
    if (bypass.some(r => frappe.user.has_role(r))) return;
    if (!frappe.user.has_role('Branch User')) return;

    frm.set_df_property('is_pos',           'hidden', 1);  // Include Payment (POS)
    frm.set_df_property('is_debit_note',    'hidden', 1);  // Is Rate Adjustment Entry
    frm.set_df_property('payment_due_date', 'hidden', 1);  // Payment Date

    // Hide Taxes & Charges section entirely
    frm.toggle_display('taxes_section_break', false);
    frm.toggle_display('taxes',               false);
    frm.toggle_display('taxes_and_charges',   false);
}
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) { rmax_branch_user_hide(frm); }
});
```

**Server-side belt:** existing permlevel-1 / Property Setter scaffolding around `update_stock` is precedent. For `is_pos` / `is_debit_note` we rely on JS hide — the underlying field stays writable for bypass roles.

### B.2 Print enable for Branch User

Audit `setup.py::BRANCH_USER_PERMISSIONS`. For Sales Invoice and Delivery Note rows ensure `print=1`. Re-run `after_migrate`.

`branch_user_restrict.js::ALLOWED_DOCTYPES` already contains both — no change.

### B.3 Customer dialog Arabic name

Extend `public/js/create_customer.js`:

- Add field `customer_name_ar` (Data) immediately after `customer_name`
- On submit map to `custom_customer_name_ar`
- Keep `customer_name` mandatory as today; AR optional

### B.4 Customer search by Arabic name

Property Setter on Customer:

| Property | Value |
|----------|-------|
| `search_fields` | `customer_name,custom_customer_name_ar,customer_id,tax_id` |

Frappe's `frappe.client.get_list` link autocomplete reads `search_fields` and matches against AR tokens. No custom controller needed.

---

## 5. Section C — DN + Return Consolidation (Net-off Mode)

### C.1 New whitelisted API

**File:** `rmax_custom/api/delivery_note.py`

```python
@frappe.whitelist()
def consolidate_dns_to_si(delivery_note_names):
    """Consolidate mixed DN + Return DN batch into one Draft Sales Invoice
    with net-off by item_code."""
    if isinstance(delivery_note_names, str):
        delivery_note_names = json.loads(delivery_note_names)
    if not delivery_note_names:
        frappe.throw(_("Select at least one Delivery Note"))

    dns = [frappe.get_doc("Delivery Note", n) for n in delivery_note_names]
    _validate_consolidation_batch(dns)
    buckets = _net_items_across_dns(dns)
    si = _build_consolidated_si(dns, buckets)
    si.insert(ignore_permissions=False)

    for dn in dns:
        frappe.db.set_value("Delivery Note", dn.name,
                            "custom_consolidated_si", si.name,
                            update_modified=False)

    return si.name
```

### C.2 Validation rules

```python
def _validate_consolidation_batch(dns):
    if any(d.docstatus != 1 for d in dns):
        frappe.throw(_("All Delivery Notes must be submitted"))

    for d in dns:
        existing = d.get("custom_consolidated_si")
        if existing and frappe.db.exists("Sales Invoice",
                                         {"name": existing, "docstatus": ["!=", 2]}):
            frappe.throw(_("DN {0} already linked to non-cancelled SI {1}")
                         .format(d.name, existing))

    keys = ["customer", "company", "currency", "branch"]
    first = {k: dns[0].get(k) for k in keys}
    for d in dns[1:]:
        for k in keys:
            if d.get(k) != first[k]:
                frappe.throw(_("DN {0} mismatched on {1}: expected {2}, got {3}")
                             .format(d.name, k, first[k], d.get(k)))
```

### C.3 Net algorithm

```python
def _net_items_across_dns(dns):
    """Group rows by (item_code, uom). Return DN qty/amount subtract from positive DN.
    
    ERPNext stores Return DN qty as NEGATIVE on disk. We use abs() + sign indicator
    to be robust even if upstream changes sign convention.
    """
    buckets = {}
    for dn in dns:
        sign = -1 if dn.is_return else 1
        for row in dn.items:
            key = (row.item_code, row.uom)
            b = buckets.setdefault(key, {
                "qty": 0, "amount": 0, "uom": row.uom,
                "src_rows": [],
            })
            qty    = sign * abs(row.qty or 0)
            amount = sign * abs(row.amount or (row.qty * row.rate) or 0)
            b["qty"]    += qty
            b["amount"] += amount
            b["src_rows"].append({"dn": dn.name, "row": row.name})
    return buckets
```

Buckets with `net_qty <= 0` are skipped; a `frappe.msgprint` summary lists skipped items so operator can audit.

### C.4 SI builder

```python
def _build_consolidated_si(dns, buckets):
    is_inter_company = bool(dns[0].get("custom_is_inter_company"))

    if is_inter_company:
        # Reuse existing inter-company-aware path so PI auto-creation remains intact.
        from rmax_custom.inter_company_dn import _build_inter_company_si_from_buckets
        return _build_inter_company_si_from_buckets(dns, buckets)

    si = frappe.new_doc("Sales Invoice")
    si.customer       = dns[0].customer
    si.company        = dns[0].company
    si.currency       = dns[0].currency
    si.branch         = dns[0].branch
    si.set_warehouse  = dns[0].set_warehouse
    si.update_stock   = 0   # DNs already moved stock
    si.posting_date   = today()
    si.due_date       = today()

    # Inherit taxes from first non-return DN
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
        # First source DN/row for traceability
        src = b["src_rows"][0]
        si.append("items", {
            "item_code": item_code,
            "qty": b["qty"],
            "uom": uom,
            "rate": rate,
            "delivery_note": src["dn"],
            "dn_detail":     src["row"],
        })

    return si
```

`inter_company_dn.py` extracts `_build_inter_company_si_from_buckets` from the existing `create_si_from_multiple_dns` so net-off mode and original positive-only mode both reuse it.

### C.5 Custom Field

| DocType | Fieldname | Type | Notes |
|---------|-----------|------|-------|
| Delivery Note | `custom_consolidated_si` | Link → Sales Invoice | Read-only, no_copy=1, in_list_view filter |

### C.6 List action UI

`public/js/delivery_note_list.js` — add a third menu item (existing two retained for backward compatibility):

```js
listview.page.add_actions_menu_item(
    __("Consolidate to Sales Invoice (Net Returns)"),
    () => _rmax_consolidate_dns(listview),
);

function _rmax_consolidate_dns(listview) {
    const selected = listview.get_checked_items().map(r => r.name);
    if (!selected.length) {
        frappe.msgprint(__("Select at least one Delivery Note first."));
        return;
    }
    frappe.confirm(
        __("Consolidate {0} Delivery Note(s) into one Sales Invoice with returns netted off?",
           [selected.length]),
        () => frappe.call({
            method: "rmax_custom.api.delivery_note.consolidate_dns_to_si",
            args: { delivery_note_names: selected },
            freeze: true,
            freeze_message: __("Building Sales Invoice..."),
            callback: r => {
                if (r.message) {
                    frappe.show_alert({ message: __("Created {0}", [r.message]),
                                        indicator: "green" });
                    frappe.set_route("Form", "Sales Invoice", r.message);
                }
            }
        })
    );
}
```

### C.7 Cancel symmetry

Extend SI `on_cancel` hook (currently `inter_company_dn.sales_invoice_on_cancel`):

```python
def sales_invoice_on_cancel(doc, method=None):
    # Existing inter-company stamp clear
    ...
    # NEW: clear custom_consolidated_si on every DN linked to this SI
    linked_dns = frappe.get_all("Delivery Note",
                                filters={"custom_consolidated_si": doc.name},
                                pluck="name")
    for dn in linked_dns:
        frappe.db.set_value("Delivery Note", dn,
                            "custom_consolidated_si", None,
                            update_modified=False)
```

DNs become eligible for re-consolidation immediately after the linked SI is cancelled.

---

## 6. Section D1 — DN Source Warehouse Auto-set

**Client JS** — `public/js/delivery_note_doctype.js` (extend existing file):

```js
frappe.ui.form.on('Delivery Note', {
    refresh(frm) {
        if (frm.is_new() && !frm.doc.set_warehouse) {
            frappe.call({
                method: "rmax_custom.branch_defaults.get_user_branch_warehouses",
                callback: r => {
                    if (r.message && r.message.length) {
                        frm.set_value('set_warehouse', r.message[0]);
                    }
                }
            });
        }
    }
});
```

**Server fallback** — `branch_defaults.set_warehouse_from_branch` already exists; register on Delivery Note `before_insert`:

```python
doc_events = {
    "Delivery Note": {
        "before_insert": "rmax_custom.branch_defaults.set_warehouse_from_branch",
        ...
    },
}
```

Server fallback covers headless API insertions where the JS path doesn't fire.

---

## 7. Section D2 — Stock User Dashboard Permission Audit

**Status:** Deferred until concrete failing-tile list arrives, OR run audit script standalone.

**Audit framework:**

1. Enumerate every `action_card` in `rmax_dashboard.js::render_stock_dashboard`
2. For each destination doctype, verify Stock User Custom DocPerm row carries appropriate flags (`read+write+create+print+submit` per the doctype's nature)
3. Verify `branch_user_restrict.js::ALLOWED_DOCTYPES` includes the destination
4. Patch gaps in `setup.py::STOCK_USER_EXTRA_PERMISSIONS`
5. Re-run `after_migrate`

**Recommended next step:** spawn standalone task once client provides the specific failing tiles or after we run the audit ourselves.

---

## 8. Files Touched

| File | Section | Change |
|------|---------|--------|
| `rmax_custom/print_helpers.py` | A | new `get_invoice_title` helper |
| `rmax_custom/rmax_custom/print_format/rmax_tax_invoice_zatca/rmax_tax_invoice_zatca.json` | A | bilingual title, customer block, pagination footer, CSS — primary target |
| `rmax_custom/rmax_custom/print_format/rmax_tax_invoice/rmax_tax_invoice.json` | A | optional sibling format — apply same updates if still in active use |
| `rmax_custom/fixtures/custom_field.json` | A, C | Customer + Address + DN custom fields |
| `rmax_custom/fixtures/property_setter.json` | A, B | Customer.search_fields, SI Branch User fields |
| `rmax_custom/public/js/sales_invoice_doctype.js` | B | role-gate hide branch-user fields + taxes section |
| `rmax_custom/public/js/create_customer.js` | B | Arabic name field in dialog |
| `rmax_custom/setup.py` | B | Branch User SI/DN `print=1` |
| `rmax_custom/api/delivery_note.py` | C | new `consolidate_dns_to_si` |
| `rmax_custom/inter_company_dn.py` | C | extract `_build_inter_company_si_from_buckets` |
| `rmax_custom/public/js/delivery_note_list.js` | C | new menu item |
| `rmax_custom/public/js/delivery_note_doctype.js` | D1 | source WH auto-set |
| `rmax_custom/branch_defaults.py` | D1 | reuse `set_warehouse_from_branch` for DN before_insert |
| `rmax_custom/hooks.py` | A, D1 | register Jinja method + DN before_insert |

## 9. Hooks Registered

```python
doc_events = {
    "Delivery Note": {
        "before_insert": "rmax_custom.branch_defaults.set_warehouse_from_branch",
        # ... existing handlers retained
    },
    "Sales Invoice": {
        # on_cancel already present; extend implementation per §C.7
    },
}

jinja = {
    "methods": [
        # ... existing entries,
        "rmax_custom.print_helpers.get_invoice_title:get_rmax_invoice_title",
    ],
}
```

## 10. Testing

### A. Print Format

| # | Scenario | Expected |
|---|----------|----------|
| A-T1 | B2C customer (no `tax_id`) | Title "Simplified Tax Invoice / فاتورة ضريبية مبسطة" |
| A-T2 | B2B customer (`tax_id` present, `custom_is_b2c=0`) | Title "Tax Invoice / فاتورة ضريبية" |
| A-T3 | `custom_is_b2c=1` overrides tax_id presence | Simplified |
| A-T4 | Customer with Arabic name only | AR block renders, EN absent |
| A-T5 | Customer with both names | EN row + AR row stacked |
| A-T6 | 5-item invoice | Fits 1 A4 with footer + terms |
| A-T7 | 7-item invoice | Spans 2 pages, header repeats, footer "Page 1 / 2" + "Page 2 / 2" |
| A-T8 | Address with AR fields | AR address renders RTL |

### B. Sales Invoice Tuning

| # | Scenario | Expected |
|---|----------|----------|
| B-T1 | Login as Branch User → New SI | `is_pos`, `is_debit_note`, `payment_due_date` hidden; Taxes section invisible |
| B-T2 | Login as Sales Manager → New SI | All fields visible |
| B-T3 | Branch User opens submitted SI | Print menu shows; print dialog opens; ZATCA format renders |
| B-T4 | New customer dialog as Branch User | `customer_name_ar` field present |
| B-T5 | Customer search "احمد" | Returns matched customer via `custom_customer_name_ar` |

### C. Consolidation

| # | Scenario | Expected |
|---|----------|----------|
| C-T1 | 3 DNs (qty 100/50/30) + 1 Return DN (qty 40 vs DN-1) | SI net qty = 140, single row per item |
| C-T2 | Mixed customers across batch | Throw "DN X mismatched on customer" |
| C-T3 | All-positive batch (no returns) | Behaves like classic Create SI from DN |
| C-T4 | All-return batch (net qty negative) | All rows skipped, msgprint summary, SI build aborts |
| C-T5 | Inter-company batch (`custom_is_inter_company=1`) | Routes to inter-company path; PI auto-creates on buying side |
| C-T6 | SI cancel | Linked DNs' `custom_consolidated_si` cleared, eligible for re-batch |
| C-T7 | DN already consolidated | Throw "DN X already linked to SI Y" |

### D1

| # | Scenario | Expected |
|---|----------|----------|
| D1-T1 | New DN as Branch User (single Branch Config) | `set_warehouse` pre-fills row 1 |
| D1-T2 | New DN as multi-branch Stock Manager | No auto-fill (no single default) |
| D1-T3 | Headless `frappe.client.insert` of DN by Branch User | Server fallback fills `set_warehouse` |

## 11. Migration / Deployment

```bash
# DEV (rmax_dev2)
git pull
sudo -u v15 bench --site rmax_dev2 migrate
sudo -u v15 bench --site rmax_dev2 clear-cache

# UAT (rmax-uat2.enfonoerp.com — bench migrate blocked)
git pull
sudo -u v15 bench --site rmax-uat2.enfonoerp.com execute frappe.utils.fixtures.sync_fixtures
sudo -u v15 bench --site rmax-uat2.enfonoerp.com execute rmax_custom.setup.after_migrate
sudo -u v15 bench --site rmax-uat2.enfonoerp.com clear-cache

# PROD (rmax.enfonoerp.com)
git pull
sudo -u frappe bench --site rmax.enfonoerp.com migrate
sudo -u frappe bench --site rmax.enfonoerp.com clear-cache
```

`sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web` after each site, per project deploy convention.

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Print format ZATCA QR refactor breaks QR rendering | Snapshot existing QR Jinja block, copy verbatim into new layout, render diff-test on existing SI |
| Customer.search_fields PS conflicts with `fateh_trading` PS | Check fixture order in `hooks.py::fixtures` filter; rmax_custom loads after fateh, last-write-wins |
| Net algorithm sign convention drift across ERPNext upgrades | `abs(qty)` + explicit `sign` indicator; covered by C-T1 / C-T4 tests |
| DN list 3 menu items overflow on small screens | Frappe groups under "Actions" dropdown automatically; no custom UI needed |
| Branch User clicks Print but format not whitelisted in `Print Settings` | Verify `RMAX Tax Invoice ZATCA` is non-letterhead-only; add to print_format_for option list if needed |
| Customer Arabic name appears in autocomplete but search returns 0 | Frappe `like %term%` against `customer_name` only by default; PS update fixes this |

## 13. Open Questions

1. **Mobile in Arabic-Indic numerals?** Default Latin (`+966-XXX-XXXXXXX`); switch to Arabic-Indic (`٠٠٩٦٦-٠٥٠-٠٠٠٠٠٠٠`) only if client confirms preference.
2. **C.4 weighted-average rate** — when same item across DNs has different rates, output single row with weighted average. Acceptable, or reject batches with rate variance > X%?
3. **C.4 inter-company trigger field** — current implementation reads `dns[0].custom_is_inter_company`. Confirm: is it ever the case that a batch could mix inter-company and non-inter-company DNs? If yes, validate single-mode and reject mixed.
4. **B.2 Branch User Print** — confirm current `BRANCH_USER_PERMISSIONS` row for Sales Invoice has `print=0`. Need to verify in setup.py before patch.

## 14. Success Criteria

- All 5 docx items in §A produce a B2C-correct Simplified Tax Invoice + B2B Tax Invoice on the same print format
- All 4 docx items in §B fully hide for Branch User, fully visible for Sales Manager
- §C.1 menu item produces a single Draft SI from any mix of DN + Return DN, with net-off applied
- §D1 New DN form auto-fills source warehouse for single-branch users
- §D2 audit completed and gaps patched (per follow-up task)
