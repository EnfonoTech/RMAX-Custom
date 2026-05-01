# RMAX Custom — Agent Context

> **This file contains everything an AI agent needs to continue working on this project.**

## Project Overview

RMAX Custom is a Frappe/ERPNext v15 custom app for RMAX's multi-branch trading/distribution business in Saudi Arabia. It extends ERPNext with branch-based access control, POS payment flows, inter-company automation, stock transfer workflows, and Material Request enhancements.

**Dev site:** rmax_dev2 on RMAX Server (5.189.131.148, `/home/v15/frappe-bench`)
**Dev URL:** rmax-dev.fateherp.com
**UAT site:** rmax-uat2.enfonoerp.com on AQRAR Server (185.193.19.184, `/home/v15/frappe-bench`)
**Repo:** github.com/EnfonoTech/RMAX-Custom (branch: main)
**Docs:** https://rmax-docs.vercel.app
**Docs source:** /Users/sayanthns/Documents/RMAX/rmax-docs/

> Every code change ships to BOTH servers. See *Deployment* below.

---

## Deployment

Two servers. Deploy to both on every merge to `main`.

| Site | Server | Server ID | Bench path | Git remote |
|------|--------|-----------|-----------|-----------|
| rmax_dev2 | RMAX (5.189.131.148) | `41ef79dc-a2fd-418a-bd88-b5f5173aeaf7` | `/home/v15/frappe-bench` | `upstream` |
| rmax-uat2.enfonoerp.com | AQRAR (185.193.19.184) | `3beb2d91-86d1-4d2d-ba0b-30955992455c` | `/home/v15/frappe-bench` | `upstream` |

### Server Manager API
```bash
# API base
http://207.180.209.80:3847
# Token (stored on orchestrator)
ssh root@207.180.209.80 "grep AGENT_SECRET /opt/server-manager-agent/.env"
# Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3

# Run command on a server
curl -s -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"command": "..."}' \
  http://207.180.209.80:3847/api/servers/<server-id>/command
```

### Deploy sequence (per server)
1. `git push origin main` (local)
2. `cd apps/rmax_custom && sudo -u v15 git pull upstream main`
3. **Dev:** `sudo -u v15 bench --site rmax_dev2 migrate` (schema / fixture changes)
4. **UAT:** `bench migrate` is blocked by a missing v11 ERPNext patch. For non-schema changes run `sudo -u v15 bench --site rmax-uat2.enfonoerp.com execute rmax_custom.setup.after_migrate` instead. For new DocTypes use `bench execute frappe.reload_doc --kwargs '{"module":"Rmax Custom","dt":"doctype","dn":"<snake_case_name>"}'`, then `bench execute frappe.custom.doctype.custom_field.custom_field.create_custom_fields` for new Custom Fields.
5. `sudo -u v15 bench --site <site> clear-cache`
6. `sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web`

`bench build` is blocked outside the 2–5 AM IST maintenance window. Use `doctype_js` for immediate client-side effect. `app_include_js` asset files served directly under `/assets/rmax_custom/js/` do not need a rebuild.

---

## Architecture

### Key Files

| File | Purpose |
|------|---------|
| `hooks.py` | App config: JS includes, doc_events, permission_query_conditions, fixtures, after_migrate |
| `__init__.py` | Imports + applies monkey patches at worker startup (LCV GL split) |
| `setup.py` | `after_migrate`: Custom DocPerms, standard-perm preservation, module profiles, VAT override permlevel perms, HR + LCV defaults kickoff |
| `boot.py` | `boot_session`: restricts Branch/Stock/Damage users to `rmax-dashboard`, sets allowed modules/workspaces |
| `branch_defaults.py` | `before_validate` hook: overrides cost center on SI/PI/PE/DN/PR for branch users |
| `branch_filters.py` | `permission_query_conditions`: filters list views by branch warehouses |
| `inter_company.py` | `on_submit` hook: auto-creates Purchase Invoice from inter-company Sales Invoice (ERPNext multi-company — distinct from inter-branch below) |
| `inter_branch.py` | Inter-Branch R/P module: branch dimension setup, COA groups + lazy leaves, JE auto-injector (Journal Entry.validate), Stock Entry hooks (on_submit / on_cancel), Stock Transfer companion JE, reconciliation report helper |
| `hr_defaults.py` | Employee Grades + Salary Components + `RMAX Sponsorship KSA` salary structure per company |
| `lcv_template.py` | LCV Charge Template setup, PR checklist auto-populate, LCV on_submit status rollup, load/create APIs |
| `landed_cost.py` | Helper: `get_based_on_field` for standard Qty/Amount distribution |
| `overrides/landed_cost_voucher.py` | LCV controller override — CBM distribution when `custom_distribute_by_cbm = 1` |
| `overrides/landed_cost_gl.py` | Monkey-patch of ERPNext `get_item_account_wise_additional_cost` for multi-tax CBM GL split |
| `api/customer.py` | VAT duplicate enforcement + override (Sales Manager), `create_customer_with_address`, VAT / phone validators |
| `api/material_request.py` | APIs: `can_create_stock_transfer`, `create_stock_transfer_from_mr`, available qty |
| `api/dashboard.py` | `get_dashboard_data` for `rmax-dashboard` page (branch/stock/damage views) |
| `branch_configuration.py` | Core: auto-manages User Permissions, upgrades Website→System user, role assignment, company default CC |
| `stock_transfer.py` | Workflow validation: branch-based approval, self-approval prevention |
| `material_request_doctype.js` | doctype_js: hide standard buttons, add Stock Transfer button |
| `purchase receipt.js` | doctype_js (note the space): Final GRN button + LCV Checklist buttons + dashboard indicator |
| `sales_invoice_doctype.js` | doctype_js: update_stock defaults + warehouse prefill + Branch User lock, credit-note auto-negate qty |
| `warehouse_pick_list.py` / `.js` | Warehouse Pick List: get_pending_items API, mark_completed, available qty color-coding |

### Permission System (5 Layers)

1. **User Permissions** (from Branch Configuration) — Company, Branch, Warehouse, Cost Center
2. **Custom DocPerm** (from setup.py) — which DocTypes Branch User can access
3. **permission_query_conditions** (branch_filters.py) — SQL WHERE for list filtering
4. **Cost center override** (branch_defaults.py) — replaces inaccessible cost centers
5. **ignore_user_permissions** (Property Setters) — on fields that reference cross-branch data

### Property Setters (ignore_user_permissions)

These are CRITICAL — without them, Frappe blocks opening documents that reference warehouses/cost centers from other branches:

- `Item Default`: default_warehouse, buying_cost_center, selling_cost_center
- `Material Request`: set_warehouse, set_from_warehouse
- `Material Request Item`: warehouse, from_warehouse, cost_center
- `Stock Transfer`: set_source_warehouse, set_target_warehouse (in DocType JSON)
- `Stock Entry`: from_warehouse, to_warehouse
- `Stock Entry Detail`: s_warehouse, t_warehouse, cost_center

### Branch Configuration Auto-Actions

When saved, creates per user:
- User Permission: Company (is_default=1)
- User Permission: Branch
- User Permission: Warehouse (first=default, rest=access)
- User Permission: Cost Center (first=default, rest=access)
- User Permission: Company default cost center (is_default=0, for tax templates)
- Role assignment (Branch User / Stock User / Stock Manager per dropdown)

Multi-branch: second branch gets is_default=0 (no duplicate default error).

### Workflow: Stock Transfer

States: Draft → Waiting for Approval → Approved (docstatus=1) / Rejected
Allowed roles: Branch User, Stock User, Stock Manager
Validation (Python):
- Only target branch users can approve/reject
- Creator cannot self-approve
- On approve: auto-creates Stock Entry (Material Transfer)

### MR → Stock Transfer Flow

1. Requester (target branch) creates MR: FROM source → TO their branch
2. Source branch user sees MR → "Create → Stock Transfer" button (checks `can_create_stock_transfer` API)
3. Source user creates ST (pre-filled from MR) → sends for approval
4. Target branch user approves → Stock Entry created

### Sales Invoice Defaults

- New SI: `update_stock = 1` and `set_warehouse` prefilled from the user's default Warehouse User Permission (via `sales_invoice_doctype.js`).
- `update_stock` is **read-only for plain Branch Users**. Any user who also carries `Sales Manager`, `Sales Master Manager`, `Stock Manager`, `System Manager`, or is Administrator can still toggle it.
- Server-side `enforce_update_stock_permission` was removed — the JS lock is intentional, so admins can bulk-import via `frappe.client.save` freely.

### Customer VAT Duplicate Override

- Two Custom Fields on Customer (permlevel=1): `custom_allow_duplicate_vat` (Check), `custom_duplicate_vat_reason` (Small Text, mandatory when checkbox is on).
- permlevel=1 write granted only to `Sales Manager`, `Sales Master Manager`, `System Manager` via `setup_vat_duplicate_override_perms()` in `after_migrate`. Other roles cannot see or tick the override.
- Enforcement layers:
  1. `Customer.validate` → `rmax_custom.api.customer.enforce_vat_duplicate_rule` — final gate, role + reason checked server-side.
  2. `rmax_custom.api.customer.validate_vat_customer` + `create_customer_with_address` — whitelisted endpoints re-check role when `allow_duplicate_vat` is passed.
  3. `vat_validation.js` + `create_customer.js` — forward the flag, hide fields from non-authorised users, skip the client dedup check when override is set.
- VAT must be 15 digits. `customer_type = "Branch"` bypasses the whole rule.

### HR Defaults

`rmax_custom.hr_defaults` runs in `after_migrate`. No-op if `hrms` app is not installed.

- Employee Grades: `Sponsorship`, `Non-Sponsorship` (global).
- Salary Components: `Basic`, `Housing Allowance`, `Transportation Allowance`, `Food Allowance`, `Other Allowance`, `GOSI Employee` (Deduction).
- Salary Structures: one Draft `RMAX Sponsorship KSA - <CompanyAbbr>` per Company. Earnings = `base × 0.60/0.25/0.10/0.05` split. Non-Sponsorship ships without a default structure.
- Strictly idempotent — once a row exists, `setup_hr_defaults()` never touches it again. Manual implementation edits survive every `bench migrate` / `after_migrate` run.
- Reset helper for admins: `bench --site <site> execute rmax_custom.hr_defaults.reset_sponsorship_salary_structures --kwargs '{"force": 1}'`. Refuses to delete submitted structures or ones assigned to an employee.

### Landed Cost Voucher

#### CBM distribution under "Distribute Manually"

Custom field on LCV `custom_distribute_by_cbm` (Check) + `custom_cbm` on Landed Cost Item. When both `distribute_charges_based_on = "Distribute Manually"` AND `custom_distribute_by_cbm = 1`:

- [`overrides/landed_cost_voucher.py`](rmax_custom/overrides/landed_cost_voucher.py) distributes `total_taxes_and_charges` across items by the `custom_cbm` ratio, skipping the standard "only one Applicable Charges" validation.
- [`overrides/landed_cost_gl.py`](rmax_custom/overrides/landed_cost_gl.py) monkey-patches `erpnext.stock.doctype.purchase_receipt.purchase_receipt.get_item_account_wise_additional_cost` at import time (from `rmax_custom/__init__.py`) so multiple tax rows under Manual mode split correctly across expense accounts using the `custom_cbm` basis. Without this patch, each tax row re-adds the full `applicable_charges` per item → GL credit doubles.

#### Charge Template + PR Checklist (rmax_custom.lcv_template)

Ships a reusable charge list and per-PR checklist so operators can track whether every charge has been booked for a Purchase Receipt.

- **New DocTypes:** `LCV Charge Template`, `LCV Charge Template Item` (child), `Purchase Receipt LCV Checklist` (child on PR).
- **Chart of Accounts:** `after_migrate` creates a group `Landed Cost Charges - <abbr>` under `Indirect Expenses` per root Company and 11 leaf expense accounts (Freight Sea/Air — USD; Duty, DO Charges, Port Charges, Mawani, Fasah Appointment Fees, Custom Clearance Charges, Transportation to Warehouse, Doc Charges, Local Unloading Expense, Overtime Kafeel — all SAR). Child Companies inherit via ERPNext sync. Existing accounts are only re-stamped with `account_currency` if they have no GL history.
- **Shipped template:** `Standard Import KSA` (is_default=1) — 11 rows, amounts blank (filled per shipment), `distribute_by = CBM` for all except `Duty = Value`.
- **PR custom fields:** `custom_lcv_template` (Link), `custom_lcv_status` (Select: Not Started / Pending / Partial / Complete, in list view + standard filter), `custom_lcv_checklist` (Table). All three carry `allow_on_submit = 1` so operators can set / switch the template on already-submitted PRs.
- **Auto-populate:** `Purchase Receipt.validate` copies template rows into the checklist when it is empty, resolving accounts per company abbr.
- **Auto-tick:** `Landed Cost Voucher.on_submit` matches every linked PR's checklist against the LCV's taxes rows by expense account, ticks rows done, stores LCV name + amount, and refreshes status. `on_cancel` reverses only rows tied to that LCV.
- **Status rollup:** 0 done → Not Started; all done → Complete; mandatory all done with optional still pending → Partial; otherwise → Pending.
- **UX:** `purchase receipt.js` adds a dashboard indicator (grey / red / orange / green with `done/total`), a `Load LCV Template` dialog button, and a `Create LCV from Template` button that spawns a Draft LCV with only the still-pending charges (CBM-only batches switch to Distribute Manually + `custom_distribute_by_cbm = 1`).
- **Whitelisted APIs:** `rmax_custom.lcv_template.load_template_into_pr`, `rmax_custom.lcv_template.create_lcv_from_template`.

### Damage Workflow

**DocTypes:** Damage Slip (DS-#####), Damage Transfer (DT-#####, submittable)
**Child Tables:** Damage Slip Item, Damage Transfer Item, Damage Transfer Slip
**Roles:** Damage User (restricted like Branch User), Branch User, Stock User can also access

**Flow:**
1. Branch user creates **Damage Slip** — records damaged items with branch warehouse + damage warehouse (Damage Jeddah/Riyadh)
2. Damage user creates **Damage Transfer** — pulls in pending slips, validates inspection (≥1 image + supplier code per item)
3. On submit: auto-creates **Stock Entry (Material Transfer)** — branch WH → damage WH
4. Admin can later **Write Off** via button — creates **Stock Entry (Material Issue)** — Dr Damage/Loss Account, Cr Stock Account

**Damage Warehouses:** `Damage Jeddah - CNC`, `Damage Riyadh - CNC` (under parent `Damage - CNC`)
**JS warehouse filter:** `name: ["like", "Damage%"]` in damage_warehouse field query

**Key Files:**
- `damage_slip/damage_slip.py` — validation, status management
- `damage_transfer/damage_transfer.py` — `_create_transfer_stock_entry()`, `write_off_damage()`, `get_pending_damage_slips()`
- `damage_transfer/damage_transfer.js` — inspection UI, slip fetching, warehouse query setup
- `damage_slip/damage_slip.js` — warehouse query setup

**Permissions:**
- Damage User: read/write/create on Damage Slip; read/write/submit on Damage Transfer
- `ignore_user_permissions: 1` on branch_warehouse, damage_warehouse, company fields
- setup.py adds 9 extra DocType permissions for Damage User (User Permission, Customer, Supplier, etc.)
- `branch_user_restrict.js` includes Damage Slip, Damage Transfer, Supplier Code in ALLOWED_DOCTYPES

**Supplier Code:** Custom DocType linking supplier name to a code. Records created for: Clear Desk, Clear Desk USD, Clear light, RMAX.

**Company Config Needed:** `custom_damage_loss_account` field on Company — required for write-off Stock Entry. Not yet configured.

### List Filtering Logic

`get_branch_warehouse_condition()` checks `tabBranch Configuration User` (NOT roles, NOT User Permissions) as source of truth. Returns warehouses from user's branch configs.

Filter per DocType:
- SI/PI/DN/PR: set_warehouse OR item warehouse matches, OR owner
- ST: set_source_warehouse OR set_target_warehouse matches, OR owner
- MR: set_warehouse OR set_from_warehouse matches, OR owner
- PE/Quotation: owner only

Admin/Stock Manager/System Manager bypass all filters.

### Warehouse Dropdown Logic

| DocType | Source WH | Target WH |
|---------|----------|-----------|
| Stock Transfer | User's branch WHs only (explicit JS filter) | Any WH (ignore_user_permissions) |
| Material Request | Any WH (ignore_user_permissions) | User's branch WHs only (explicit JS filter) |

Both use `frappe.call` to fetch permitted WHs then filter with `name: ["in", permitted]` + `ignore_user_permissions: 1` to override Frappe's default single-value filter.

---

### Inter-Branch Receivables & Payables (single-company multi-branch GL)

Implementation: `rmax_custom/inter_branch.py`. Branch on the new build is treated as an Accounting Dimension enforced per Company at the GL-posting layer.

**Branch:** `feature/inter-branch-rp-phase1` (deployed on `rmax_dev2`, NOT yet merged to `main`, NOT on UAT).

**Plan + user guide**
- Plan: `docs/superpowers/plans/2026-04-28-inter-branch-rp-foundation.md`
- User guide: `docs/user-guides/inter-branch-receivables-payables.md`

**Custom Fields**
- `Journal Entry Account.custom_auto_inserted` (Check, read-only) — flag for auto-injected legs
- `Journal Entry Account.custom_source_doctype` (Link → DocType) — source traceability (child)
- `Journal Entry Account.custom_source_docname` (Dynamic Link → custom_source_doctype) — source traceability (child)
- `Journal Entry.custom_source_doctype` (Link → DocType, header) — denormalised mirror; powers Connections sidebar finder
- `Journal Entry.custom_source_docname` (Dynamic Link, header) — denormalised mirror; finder lookup field
- `Company.custom_inter_branch_cut_over_date` (Date) — injector skips entries dated before this. Empty = injector disabled for that company.
- `Company.custom_inter_branch_bridge_branch` (Link → Branch) — required for 3+ branch JEs; bridge branch becomes implicit counterparty for every other branch in the entry.

**Chart of Accounts**
- Per root Company: `Inter-Branch Receivable` (Asset, group, under Current Assets) + `Inter-Branch Payable` (Liability, group, under Current Liabilities). Created by `setup_inter_branch_foundation()` from `setup.after_migrate`. Only iterates root companies — ERPNext's `validate_root_company_and_sync_account_to_children` propagates to children.
- Lazy leaves per counterparty: `Due from <Branch>` (under Receivable group) + `Due to <Branch>` (under Payable group). Created on demand by `get_or_create_inter_branch_account()`.
- New Branch's `after_insert` hook creates leaves both directions for every existing Branch (via `on_branch_insert`).

**Auto-injector** (`auto_inject_inter_branch_legs`)
- Hook: `Journal Entry.validate` (chained AFTER `bnpl_clearing_guard.warn_bnpl_clearing_overdraw`)
- Skipped when: doctype mismatch / `flags.skip_inter_branch_injection` / no company / pre cut-over
- Strips prior auto-injected rows then recomputes per-branch imbalance (idempotent on re-validate)
- Two-branch path: counterparty inferred from imbalance signs
- Three+ branch path: requires `Company.custom_inter_branch_bridge_branch` configured AND bridge present in JE; pairs every non-bridge branch against bridge. Otherwise rejects with clear error.
- Final guard: re-checks per-branch balance after injection; throws `Inter-Branch Auto-Injection Error` if any branch still imbalanced.

**Stock movement integration (two paths, both produce same accounting)**

_Path 1 — Stock Transfer wrapper (existing custom workflow):_
- `Stock Transfer.on_submit` calls `create_companion_inter_branch_je_for_stock_transfer(self)` AFTER `create_stock_entry()`
- ST sets `flags.from_stock_transfer = True` on the SE so Path 2's hook short-circuits
- Companion JE source = `Stock Transfer / ST-XXXX`
- `Stock Transfer.on_cancel` queries and cancels JEs with `custom_source_docname = ST.name`

_Path 2 — Direct Stock Entry (Material Transfer):_
- Hook: `Stock Entry.on_submit` → `on_stock_entry_submit`
- Skipped when: `flags.from_stock_transfer` / purpose ≠ Material Transfer / no company / existing JE for SE name
- Resolves each item row's `s_warehouse` + `t_warehouse` via `resolve_warehouse_branch()` (looks up Branch Configuration Warehouse mapping)
- Same-branch warehouse pair (e.g. WH-HO-1 ↔ WH-HO-2 both under HO) → no companion JE; standard SE GL is sufficient
- Cross-branch single-pair: re-tags SE's GL Entries per leg via `_retag_se_gl_entries` (source warehouse legs → branch=src; target legs → branch=tgt) + creates companion JE
- Multi-pair SE (different src/tgt across rows): logs hint to Error Log and skips (Phase 1 ops splits into one-pair-per-doc)
- Companion JE source = `Stock Entry / MAT-STE-XXXX`
- `Stock Entry.on_cancel` mirrors ST cancel

**Reconciliation report**
- Path: `rmax_custom/rmax_custom/report/inter_branch_reconciliation/`
- Frappe Script Report: matrix view rows=from_branch × cols=to_branch
- Health check: each pair (A→B + B→A) must sum to zero
- Roles: Accounts Manager / Accounts User / Auditor / System Manager
- Debug helper: `rmax_custom.inter_branch.print_reconciliation(company, from_date, to_date)` — whitelisted, prints to stdout via `bench execute`

**Branch auto-fill on stock-side validate** (`auto_set_branch_from_warehouse`)
- Hook target: Stock Entry / Stock Reconciliation / Purchase Receipt / Delivery Note / Purchase Invoice / Sales Invoice (all `validate`)
- Iterates each item row; if `branch` empty, looks up via `resolve_warehouse_branch(item.warehouse|s_warehouse|t_warehouse)` and sets it
- Header `branch` set to first row that resolves (operator override stays)
- Prevents the per-Company `mandatory_for_bs` GL rejection on opening stock and routine stock movements
- For Material Transfer SEs the source-side branch is filled via `s_warehouse`; the target-side branch on each GL leg is corrected post-submit by `_retag_se_gl_entries`

**UI surfacing — companion JE on Stock Entry / Stock Transfer**
- Server-side: `override_doctype_dashboards` registers `stock_transfer_dashboard` + `stock_entry_dashboard` (in `rmax_custom/api/dashboard_overrides.py`). Both add a "Journal Entry" connection card under "Inter-Branch" via `non_standard_fieldnames["Journal Entry"] = "custom_source_docname"`. Requires the JE header-level Custom Fields.
- Client-side: `rmax_custom/public/js/stock_entry_inter_branch.js` (registered as `doctype_js["Stock Entry"]`). On submitted Material Transfer SEs: queries `Journal Entry Account` rows with `custom_source_doctype=Stock Entry + custom_source_docname=SE.name`, adds an `Inter-Branch JE → ACC-JV-...` button per JE, and renders a sidebar "Inter-Branch" card with click-to-navigate badges.

**Backfill helper** (`rmax_custom.inter_branch.backfill_je_header_source`)
- Whitelisted. Populates `custom_source_doctype` + `custom_source_docname` on JE header for already-submitted companion JEs created before the Phase 2 dashboard work.
- Idempotent. Only updates JEs whose header is empty AND whose child auto-injected rows agree on a single source.
- Run: `bench --site rmax_dev2 execute rmax_custom.inter_branch.backfill_je_header_source`

**Hooks registered (`hooks.py`)**
```
"Journal Entry": {
    "validate": [
        "rmax_custom.bnpl_clearing_guard.warn_bnpl_clearing_overdraw",
        "rmax_custom.inter_branch.auto_inject_inter_branch_legs",
    ],
},
"Branch": {
    "after_insert": "rmax_custom.inter_branch.on_branch_insert",
},
"Stock Entry": {
    "validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse",
    "on_submit": "rmax_custom.inter_branch.on_stock_entry_submit",
    "on_cancel": "rmax_custom.inter_branch.on_stock_entry_cancel",
},
"Stock Reconciliation": {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
"Purchase Receipt":     {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
"Delivery Note":        {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
"Purchase Invoice":     {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
"Sales Invoice":        {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
```

```
override_doctype_dashboards = {
    "Material Request":  "rmax_custom.api.dashboard_overrides.material_request_dashboard",
    "Stock Transfer":    "rmax_custom.api.dashboard_overrides.stock_transfer_dashboard",
    "Stock Entry":       "rmax_custom.api.dashboard_overrides.stock_entry_dashboard",
}

doctype_js = {
    ...,
    "Stock Entry": "public/js/stock_entry_inter_branch.js",
}
```

**Activation steps (per Company)**
1. Set `Inter-Branch Cut-Over Date` on the Company (auto-injector OFF until set).
2. Set `Inter-Branch Bridge Branch` on the Company if multi-branch (3+) JEs are needed.
3. (Auto by `after_migrate`) two parent groups + dimension config.

**Out of scope (deferred)**
- Settlement / Clearing
- Salary / Expense Claim / Vendor-on-behalf
- Branch-wise TB/P&L/BS reports beyond reconciliation
- HO overhead allocation
- Historical restate

**Bug history (deployed and fixed on dev)**
1. Initial `setup_inter_branch_foundation` iterated all companies including ERPNext children → `validate_root_company_and_sync_account_to_children` rejected. Fix: filter to `parent_company in ("", None)`.
2. Auto-injected JE Account rows had only `*_in_account_currency` fields — ERPNext's `make_gl_entries` skipped them because company-currency `debit/credit` were 0. Fix: also set `account_currency`, `exchange_rate=1`, and company-currency `debit/credit`.

---

## Known Issues & Gotchas

1. **bench build required** for `app_include_js` and `app_include_css` changes. Use `doctype_js` for immediate effect. RMAX's `app_include_js` entries point at `/assets/rmax_custom/js/*.js` which are served directly — no rebuild needed.
2. **async:false deprecated** in browsers — always use async `frappe.call` with callback.
3. **frappe.client.get_count on User Permission** fails for non-admin users — use whitelisted API instead.
4. **user_doc.add_roles()** can fail silently during Branch Config save — use direct `Has Role` insert.
5. **Property Setter / Custom Field fixtures** need BOTH: correct entry in JSON AND name in `hooks.py` fixture filter list.
6. **Duplicate default User Permission** — Frappe allows only ONE `is_default` per allow type per user. Check before setting.
7. **Rogue warehouse permissions** — old code in ST `before_save` auto-created WH permissions. REMOVED. Only Branch Config manages permissions now.
8. **ERPNext role name** is `Stock User` not `Warehouse User`.
9. **Website Users cannot hold desk roles.** `user_type = "Website User"` users silently lose Branch / Stock / Damage User role assignments — `get_roles()` returns empty. Branch Configuration now force-upgrades to `System User` before inserting `Has Role`. Apply the same upgrade in any new role-assigning code.
10. **Custom DocPerm replaces standard DocPerm.** As soon as any Custom DocPerm row exists on a doctype, Frappe ignores standard DocPerm entirely. `setup.preserve_standard_docperms_on_touched_doctypes()` mirrors every standard row into Custom DocPerm before our rmax roles are added, so Accounts Manager / Sales User / Purchase User etc. don't lose access. New doctypes in `BRANCH_USER_PERMISSIONS` / `STOCK_USER_EXTRA_PERMISSIONS` / `DAMAGE_USER_PERMISSIONS` automatically flow through this backfill.
11. **UAT migrate blocked** by `ModuleNotFoundError: erpnext.patches.v11_1.rename_depends_on_lwp`. Non-schema changes use `bench execute rmax_custom.setup.after_migrate`. Schema changes need `bench execute frappe.reload_doc` + `bench execute frappe.custom.doctype.custom_field.custom_field.create_custom_fields` as a workaround.
12. **Account currency can only be changed before first GL entry.** `_align_account_currency` in `lcv_template.py` skips accounts with any `GL Entry` row — flip currency before users book anything to the account, or expect manual cleanup (cancel offending LCVs first).
13. **LCV "Only one Applicable Charges" under Distribute Manually.** Our override skips that guard only when `custom_distribute_by_cbm = 1`. For standard Distribute Manually flows the ERPNext rule still applies (single tax row).
14. **Child table DocTypes need a controller .py** on v15 even when `istable = 1`. Frappe tries to import the controller during migrate and raises `Module import failed` if it is missing.
15. **bench execute eval vs method names.** Kwargs use the parameter names of the target callable; `frappe.db.get_all` wants `doctype` but `frappe.db.set_value` wants `dt` / `dn` / `field` / `val`.
16. **Inter-Branch leaves only on root companies.** `setup_inter_branch_foundation` filters `Company` by `parent_company in ("", None)`. ERPNext rejects accounts created directly on child companies via `validate_root_company_and_sync_account_to_children` and propagates the new account to children automatically.
17. **Auto-injected JE rows must carry company-currency `debit`/`credit`.** Setting only `debit_in_account_currency` / `credit_in_account_currency` on programmatically-appended JE Account rows leaves company-currency totals at 0, and ERPNext's `make_gl_entries` skips zero-amount rows. Always set `account_currency`, `exchange_rate`, AND the company-currency fields when injecting rows.
18. **`flags.skip_inter_branch_injection` is needed on auto-built balanced JEs.** Stock Transfer + direct Stock Entry companion JEs are intentionally one-sided per branch but globally balanced. Set `je.flags.skip_inter_branch_injection = True` BEFORE `je.insert()` so the validate hook doesn't try to add more legs.
19. **`flags.from_stock_transfer` prevents double-posting on SE.** Stock Transfer's `create_stock_entry` sets this on the new Stock Entry doc. The Stock Entry submit hook short-circuits when the flag is set so the ST hook owns companion-JE creation. Without the flag, both hooks would post duplicate companion JEs.
20. **`custom_source_docname` is a Dynamic Link** with `options = "custom_source_doctype"`. Frappe validates that the referenced document exists. Test stubs that reference non-existent docnames will raise `LinkValidationError` at JE insert. Real flows always pass a real doc name.
21. **Unmapped warehouses silently skip the inter-branch SE hook.** When ANY item row's `s_warehouse` or `t_warehouse` doesn't resolve via `resolve_warehouse_branch()`, `_stock_entry_branch_pair` returns `(None, None, 0.0)` and the companion JE is not created. The SE itself submits successfully. RMAX's Damage warehouses (`Damage Jeddah - CNC`, `Damage Riyadh - CNC`) need explicit Branch Configuration mapping. Operational policy must be set: per-city (Damage Jeddah → Jeddah branch) vs centralized (all damage WHs → HO) vs dedicated (all damage WHs → Damage branch). Without a mapping, branch-to-damage transfers do not create inter-branch obligations and reconciliation reports will under-count those movements.
22. **Companion JE inherits source valuation as-is.** `create_companion_inter_branch_je_for_stock_entry` and `_for_stock_transfer` use the source SE's `basic_amount` (or `qty * basic_rate` fallback). If the source warehouse Bin's `valuation_rate` is wrong (inflated by a bad PR / Stock Reconciliation / LCV), the JE faithfully posts that wrong number. Inter-branch is NOT the source of truth for valuation. Trace via Stock Ledger Entry → fix the upstream document → cancel + re-create the SE/ST.
23. **`auto_set_branch_from_warehouse` handles Stock Entry rows that have BOTH `s_warehouse` and `t_warehouse`.** Lookup priority is `warehouse → s_warehouse → t_warehouse`. For Material Transfer rows the source-side `s_warehouse` is selected, so the row's branch reflects the SOURCE branch. The target-side branch on the GL Entry rows is corrected post-submit by `_retag_se_gl_entries` (which queries each GL row's `account.warehouse` and sets `branch` per leg).

---

## Installed Apps on rmax_dev2

frappe 15.x, erpnext 15.x, hrms 15.x, grey_theme, ksa_compliance, fateh_trading, rmax_custom, crm

## Dependencies

- **sf_trading** — provides `apply_patch`/`restore_patch` for inter-company PI creation
- **ERPNext v15** — core ERP

---

## Test Users

| User | Branch | Warehouses | Role |
|------|--------|-----------|------|
| shameel@rmax.com | Jeddah, Warehouse Malaz | Warehouse Jeddah - CNC, Warehouse Malaz - CNC | Branch User |
| javad@rmax.com | Snowlite, Riyadh | Snow Light - CNC, Warehouse Riyadh - CNC | Branch User |
| suhailsudu@gmail.com | Jeddah | Warehouse Jeddah - CNC | Branch User |
| andru@gmail.com | Riyadh | Warehouse Riyadh - CNC | Branch User |
| warehouse@rmax.com | Warehouse Bahra | Warehouse Bahrah - CNC | Stock User |
| sabith@gmail.com | — | — | Damage User |

---

## Documentation

- **User docs:** https://rmax-docs.vercel.app (source: /Users/sayanthns/Documents/RMAX/rmax-docs/)
- **Developer docs:** DOCUMENTATION.md in repo root
- **User guide HTML:** rmax_custom/public/html/user-guide.html (accessible from site)
