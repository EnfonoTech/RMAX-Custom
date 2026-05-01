# RMAX Custom — Production Audit Findings

Run by frappe-erpnext-expert agent on `main` branch state at commit `a978430`. 30 findings total. Critical 4 fixed in commit `f4b9991`. Open items tracked here.

Severity legend: 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM | ⚪ LOW

---

## CRITICAL (FIXED ✓)

| # | Issue | Fix Commit |
|---|-------|------------|
| 1 | `hooks.py` duplicate `doc_events` keys → Python dict last-wins → BNPL uplift, branch cost-center override, branch payment-account rewrite, naming-series auto-pick, BNPL validate, inter-company auto-PI, inter-company DN consolidation + cancellation, LCV checklist auto-populate ALL silently dropped on Sales Invoice / Purchase Invoice / Delivery Note / Purchase Receipt | ✅ `f4b9991` |
| 2 | `inter_branch._stock_transfer_total_value` reads `basic_amount` / `basic_rate` from Stock Transfer Item which has no such columns → companion JE always amount=0 → ALL Stock Transfer traffic absent from inter-branch reconciliation | ✅ `f4b9991` |
| 3 | `inter_company.py` reads bare `inter_company_branch` instead of `custom_inter_company_branch` → Inter Company Branch master never consulted, auto-PI always uses fallback company default | ✅ `f4b9991` |
| 4 | No VAT Sale auto-built JE/SE rows missing `branch` field + company-currency `debit/credit` + `account_currency` + `exchange_rate` + `flags.skip_inter_branch_injection` → submission breaks once Cut-Over Date set | ✅ `f4b9991` |

---

## HIGH (open)

### #5 — Blank-branch rows silently ignored in inter-branch injector
**File**: `rmax_custom/inter_branch.py` `_per_branch_imbalance` (≈ line 239-244)
**Bug**: rows with `not br` skipped → JE with one missing-branch row passes injector's globally-balanced check while real GL ends up unbalanced per-branch. ERPNext mandatory-dimension throws later but injector's diagnostic is wrong.
**Fix**: `frappe.throw` early when any non-auto-injected row is missing branch on a multi-branch JE.

### #6 — `set_naming_series_from_branch` mutates Property Setter at request time
**File**: `rmax_custom/branch_defaults.py` `set_naming_series_from_branch` (≈ line 329-371)
**Bug**: hook writes Property Setter on every fresh branch's first insert; concurrent inserts race; Branch Users typically lack Property Setter write perm → swallowed exception → naming_series stays unset; cache clear inside request expensive.
**Fix**: pre-seed Property Setter in `after_migrate` from `Branch.custom_doc_prefix` table. Hook just reads existing options.

### #7 — Auto-injector source traceability misroutes on mixed-source rows
**File**: `rmax_custom/inter_branch.py` `auto_inject_inter_branch_legs` (≈ line 316-419)
**Bug**: picks first source-tagged row blindly. When a manual JE has its own source, injector inherits wrong source. `custom_source_docname` Dynamic Link errors on insert when source doesn't exist (gotcha #25).
**Fix**: only inherit source when ALL existing rows agree, else leave blank; validate doc existence before stamping.

### #8 — `inter_company.sales_invoice_on_submit` runs BEFORE consolidation refresh on same SI → potential PI double-count
**File**: `rmax_custom/hooks.py` Sales Invoice on_submit list ordering
**Bug**: when SI is a DN-consolidation SI, ERPNext's PI builder copies all DN-linked items at inter-company price + doesn't know stock already moved. PI may double-count when `update_stock=1`.
**Fix**: in `inter_company.sales_invoice_on_submit`, early-return when SI rows carry `delivery_note` (consolidation SI). Or remove auto-PI call entirely on consolidation SIs since DN already created the PI side via earlier flow.

### #9 — `bnpl_uplift` re-reads `custom_pos_payments_json` from DB on every save
**File**: `rmax_custom/bnpl_uplift.py` `apply_bnpl_uplift` (≈ line 81-90)
**Bug**: re-read overwrites in-memory doc.custom_pos_payments_json with stale DB version → user editing payments in form sees their fresh changes clobbered. Also adds N+1 SELECTs on bulk import.
**Fix**: only re-read when `is_pos=1 AND not doc.payments`.

### #10 — `flags.in_inter_company_pi_creation` leaks across requests on log_error throw
**File**: `rmax_custom/inter_company.py` (≈ line 13-111)
**Bug**: flag set inside try, reset only in finally. If `frappe.log_error` itself raises, flag leaks across requests on the same worker.
**Fix**: wrap flag set in try/finally immediately, before `apply_patch()`.

### #11 — Stock Entry list view unfiltered → cross-branch leakage 🔥
**File**: `rmax_custom/hooks.py` `permission_query_conditions`
**Bug**: Branch Users have read on Stock Entry but no `permission_query_conditions` registered → list view shows every company's stock entries.
**Fix**: add Stock Entry filter querying `from_warehouse` / `to_warehouse` against branch warehouses.

### #12 — SI / PI / PR Property Setters missing `ignore_user_permissions` 🔥
**File**: `rmax_custom/fixtures/property_setter.json`
**Bug**: Branch User opening a Sales Invoice / PI / PR with header `set_warehouse` referencing a global default ("Stores - CNC") hits "Not Permitted". Same exact failure pattern as Quotation / Delivery Note (already fixed). Currently only Quotation, DN, MR, ST, Stock Entry, Item Default are covered.
**Fix**: add `ignore_user_permissions=1` Property Setters on:
- `Sales Invoice-set_warehouse`, `Sales Invoice Item-warehouse`
- `Purchase Invoice-set_warehouse`, `Purchase Invoice Item-warehouse`
- `Purchase Receipt-set_warehouse`, `Purchase Receipt Item-warehouse`

### #13 — inter-branch leaf account creation no try/except, no re-validate
**File**: `rmax_custom/inter_branch.py` (≈ line 180-193)
**Bug**: if leaf account name collides with existing account (e.g. propagated from parent), `acc.insert()` raises DuplicateEntryError. No try/except → branch insert and JE validate both blow up.
**Fix**: wrap in try/except + re-resolve via `frappe.db.exists` before insert.

### #14 — `bnpl_clearing_guard` `voucher_no != %s` filter wrong on new doc
**File**: `rmax_custom/bnpl_clearing_guard.py` `_gl_balance_excluding` (≈ line 54-66)
**Bug**: on insert, `doc.name` is "new-…" or empty; SQL excludes nothing → soft warn fires on every new BNPL clearing JE.
**Fix**: when `not doc.name or startswith("new-")`, pass `voucher_no=None`. Or early-return when `docstatus=0 and not name`.

### #15 — `setup.after_migrate` partially try/except wrapped
**File**: `rmax_custom/setup.py` `after_migrate` (≈ line 186-261)
**Bug**: core helpers (`fix_stock_transfer_series`, `preserve_standard_docperms`, `setup_branch_user_permissions`, etc.) NOT try/except wrapped. Failure aborts ALL downstream. `frappe.db.commit()` mid-helper → partial fail leaves Custom DocPerm inconsistent.
**Fix**: wrap each helper individually. Move all `frappe.db.commit()` to end-of-helper.

### #16 — Module Profile creation via raw SQL bypasses cache
**File**: `rmax_custom/setup.py` `setup_branch_user_module_profile`, `setup_damage_user_module_profile` (≈ line 557-575)
**Bug**: raw `INSERT INTO tabModule Profile` works on strict-mode MariaDB but `name` auto-naming bypassed; `frappe.cache().delete_value("__module_profile")` never called → list views may not show profile for an hour.
**Fix**: `frappe.get_doc({...}).db_insert()` + `frappe.clear_cache()`.

### #17 — `pe_permission_query` ignores PE→PI/JE references
**File**: `rmax_custom/branch_filters.py` `pe_permission_query` (≈ line 151-159)
**Bug**: subquery only walks SI Item links → legitimate PEs (supplier payments, PI refunds) hidden from owners.
**Fix**: union same logic for PI references; or simplify to `owner = user OR party in user_party_perms`.

---

## MEDIUM (defer)

| # | File | Issue |
|---|------|-------|
| 18 | `inter_branch.py` `_inject_pair` | N+1 query: `frappe.db.get_value("Account", ..., "account_currency")` per JE — cache once per company |
| 19 | `hr_defaults.py` | Pin HRMS minor version — currently loose deps risk Salary Structure JSON shape drift |
| 20 | `bnpl_settlement_setup.py` `wire_bnpl_modes_of_payment` | `mop.set("accounts", [])` wipes other companies' rows — only update missing rows |
| 21 | `overrides/landed_cost_voucher.py` | Bypass-validation only when `custom_distribute_by_cbm=1`; lose ERPNext sum-check for cross-checks |
| 22 | `overrides/landed_cost_gl.py` | Patch at module-import time may miss workers depending on Frappe deployment timing — also register via `before_app_install` / `after_migrate` |
| 23 | `inter_branch.py` `backfill_je_header_source` | Whitelisted with no role check — anyone can trigger a 1000-row UPDATE |
| 24 | `inter_company_dn.py` | `db.set_value` outside doc reload → stale `custom_inter_company_si` in cached doc graph; print formats / dashboards see wrong value. Add `frappe.clear_document_cache("Delivery Note", dn.name)` |
| 25 | `lcv_template.py` (≈ line 340) | Multi-currency aggregation: `tax.amount` is in tax row's currency; sum mixes USD and SAR. Use `tax.base_amount` |

## LOW

| # | File | Issue |
|---|------|-------|
| 26 | `branch_filters.py` (multiple) | `wh_list` join on empty list → `IN ()` SQL syntax error (defensive only) |
| 27 | `no_vat_sale.py` `before_insert` | Crafted JSON POST with `approval_status="Approved"` briefly persists wrong state before validate gates |
| 28 | `api/customer.py` | VAT duplicate filter `name != ""` masks a NULL bug if Customer naming convention changes |
| 29 | `hooks.py` | `Stock Entry` `doctype_js` registered; verify `branch_user_restrict.js` ALLOWED_DOCTYPES + add Stock Entry permission query (overlap with #11) |
| 30 | `hooks.py` `doctype_js["Purchase Receipt"]` | Filename has literal SPACE (`purchase receipt.js`) — cross-platform git/zip risk; rename to `purchase_receipt.js` |

---

## Test coverage gaps

`test_inter_branch.py` covers injector + helpers but NOT:
- `auto_set_branch_from_warehouse` hook on 5 doctypes (the very thing duplicated in hooks.py — would have caught finding #1)
- `_retag_se_gl_entries` post-submit
- on_cancel symmetry of SE/ST companion JEs
- BNPL uplift cancellation
- Inter-Company DN consolidation/cancellation cycle
- NVS approval workflow
- Branch MoP rewriting in `override_payment_accounts_from_branch`
- Property Setter mutation in `set_naming_series_from_branch`

**Top priority**: load-time hook-resolution test — assert all expected hooks present after `frappe.get_hooks("doc_events")` resolution.

## ERPNext upgrade compatibility

Two monkey patches at risk:
- `overrides/landed_cost_gl.py` patches `erpnext.stock.doctype.purchase_receipt.purchase_receipt.get_item_account_wise_additional_cost`
- `overrides/landed_cost_voucher.LandedCostVoucher` subclasses ERPNext class and overrides `set_applicable_charges_on_item` + `validate_applicable_charges_for_item`

Both will silently no-op or hard-fail on ERPNext v16 if upstream renames functions or changes return-dict shape. Add `assert frappe.__version__.startswith("15.")` guard in `_apply_monkey_patches` and `LandedCostVoucher.__init_subclass__`.

## UAT-blocking workaround impact

`bench migrate` blocked on UAT (v11 ERPNext patch). Fallback (`bench execute rmax_custom.setup.after_migrate` + `frappe.utils.fixtures.sync_fixtures`) silently skips:
- DocType JSON schema reload (any new field/option in custom doctypes JSON not under `Custom Field`)
- Standard DocPerm rebuild from doctype JSON (`preserve_standard_docperms_on_touched_doctypes` reads stale `tabDocPerm`)
- `patches.txt` execution
- `bench build` (asset bundle changes can't ship to UAT outside maintenance window)

## Naming + import conventions

- `rmax_custom/no_vat_sale.py` (setup helper) and `rmax_custom/rmax_custom/doctype/no_vat_sale/no_vat_sale.py` (controller) share confusable filenames — rename setup helper to `no_vat_sale_setup.py`
- `purchase_invoice_before_validate` in `inter_company.py` is dead code (never wired in hooks)
- Verify every Custom Field referenced in code is also in fixtures (drift risk)
