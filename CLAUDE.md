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
| `inter_company.py` | `on_submit` hook: auto-creates Purchase Invoice from inter-company Sales Invoice |
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
| `api/sales_invoice_payment.py` | `get_payment_modes_with_account` (branch MoP allowlist filter) + `create_pos_payments_for_invoice` |
| `rmax_custom/doctype/no_vat_sale/no_vat_sale.py` | NVS controller — branch-warehouse guard, approval workflow APIs, JE + SE creation |
| `material_request_doctype.js` | doctype_js: hide standard buttons, add Stock Transfer button |
| `purchase receipt.js` | doctype_js (note the space): Final GRN button + LCV Checklist buttons + dashboard indicator |
| `sales_invoice_doctype.js` | doctype_js: update_stock defaults + warehouse prefill + Branch User lock, credit-note auto-negate qty, branch MoP swap on payment rows |
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
- `Quotation`: set_warehouse
- `Quotation Item`: warehouse
- `Delivery Note`: set_warehouse
- `Delivery Note Item`: warehouse, target_warehouse

### Branch Configuration Auto-Actions

When saved, creates per user:
- User Permission: Company (is_default=1)
- User Permission: Branch
- User Permission: Warehouse (first=default, rest=access)
- User Permission: Cost Center (first=default, rest=access)
- User Permission: Company default cost center (is_default=0, for tax templates)
- Role assignment (Branch User / Stock User / Stock Manager per dropdown)

Multi-branch: second branch gets is_default=0 (no duplicate default error).

### Branch Configuration — Modes of Payment (Cash/Bank allowlist)

New child table `Branch Configuration Mode of Payment` (istable=1, fields: `mode_of_payment` Link + `type` fetched from `Mode of Payment.type`). Replaces the earlier `cash_account` / `bank_account` Link fields. Multiple Cash + Bank rows allowed per branch. Form filter on the child Link constrains entries to MoPs of `type` Cash or Bank.

**Behaviour for Branch Users (only)**:
- Sales Invoice POS popup `get_payment_modes_with_account` post-filters: Cash MoPs constrained to branch's cash list; Bank MoPs to branch's bank list. BNPL / General / Phone pass through unfiltered (BNPL is common to every branch).
- `before_validate` hook `branch_defaults.override_payment_accounts_from_branch` walks `payments[*]`:
  - Cash row, MoP in branch list → keep, resync `account` from `Mode of Payment Account` for SI company.
  - Cash row, MoP NOT in branch list, branch HAS cash MoPs → swap to first allowed; resync.
  - Cash row, branch has zero cash MoPs → drop the row.
  - Same logic for Bank. Other types untouched.
- "Opt-out" rule: if branch has NO Cash AND NO Bank rows configured at all, the filter / hook are no-ops (legacy behaviour).
- Bypass roles: System Manager, Sales Manager, Sales Master Manager, Stock Manager, Administrator.

Whitelisted helper: `rmax_custom.branch_defaults.get_user_branch_accounts(user, company)` returns `{branch, cash:[{mop,account},...], bank:[{mop,account},...]}` for the JS popup.

### No VAT Sale — Sales Manager-only + Approval Workflow

Doctype: `No VAT Sale` (submittable). Posts a Journal Entry + Stock Entry on submit (cash receipt against Naseef account + COGS against `Damage Written Off (N)`).

**Access (post Apr-2026)**
- Standard DocPerm (`no_vat_sale.json`) keeps only `System Manager` + `Sales Manager`. Branch User / Stock User / Sales User / Accounts Manager all dropped.
- `setup.restrict_no_vat_sale_to_sales_manager()` runs every `after_migrate` and deletes any leftover Custom DocPerm rows on the doctype (cleanup of older deploys).
- `branch_filters.no_vat_sale_permission_query` bypasses for `Sales Manager` + `System Manager`; everyone else gets the standard branch warehouse filter.

**Approval workflow (desk, no PWA)**
- New field `approval_status` (Select: Draft / Pending Approval / Approved / Rejected) — read-only on the form, default Draft.
- `before_insert` forces Draft; `before_submit` blocks if status ≠ Approved (protects against direct `frappe.client.submit`).
- `on_update` notifies the named `approved_by` user when status flips to Pending Approval — uses `frappe.desk.form.assign_to.add` (ToDo + email); falls back to manual ToDo + `frappe.sendmail` on error.
- `on_submit` closes any open ToDos for the doc.

Whitelisted APIs:
- `submit_for_approval(name)` — Draft → Pending Approval; throws if `approved_by` empty.
- `approve_no_vat_sale(name, remarks)` — verifies caller is `approved_by` (or Sales Manager / System Manager); sets status=Approved, calls `submit()` with `flags.ignore_permissions = True` (role gate already passed).
- `reject_no_vat_sale(name, remarks)` — sets status=Rejected, keeps Draft, closes open ToDos.
- `get_branch_warehouses(branch)` — returns warehouses listed under the Branch Configuration's Warehouse child table; powers the `set_query` on `warehouse` and the server-side `_validate_branch_warehouse_match` guard.

**Branch warehouse filter**
- `_validate_branch_warehouse_match` checks Company match AND that `warehouse` is in `Branch Configuration Warehouse` rows for the selected `branch`. Throws if not.
- Form filter (`no_vat_sale.js`) re-pulls allowed warehouses on `branch` change; clears the picker if the existing warehouse falls out of scope.

**Form UI buttons (under "Approval" group)**
- `Send for Approval` (creator, Draft / Rejected): calls `submit_for_approval`.
- `Approve & Submit` (named approver only, Pending Approval): dialog with optional remarks → `approve_no_vat_sale`.
- `Reject` (named approver only, Pending Approval): dialog with mandatory reason → `reject_no_vat_sale`.

### Branch User Dashboard (rmax-dashboard) — quick action whitelist

Custom Page: `rmax_custom/page/rmax_dashboard/`. Branch User landing page configured via `role_home_page`. Accessible doctypes for restricted users gate-kept by `public/js/branch_user_restrict.js` `ALLOWED_DOCTYPES`. When adding a new dashboard tile, BOTH must be updated:
1. `rmax_dashboard.js` — add `action_card(...)` in `render_branch_dashboard` / `render_stock_dashboard`.
2. `branch_user_restrict.js` — add the doctype to `ALLOWED_DOCTYPES` or the navigation will bounce restricted users back to `rmax-dashboard`.

Current branch tile order (sales): Sales Invoice → Quotation → **Delivery Note** → Customer → Payment Entry → Purchase Receipt → Purchase Invoice → Material Request → Stock Transfer → Sales Return → Purchase Return → Report Damage → Damage Transfer.

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
16. **Frappe controller class names use raw `replace(" ","")` — NOT title-case.** For "Branch Configuration Mode of Payment" the expected class is `BranchConfigurationModeofPayment` (lowercase 'of'). Same convention as ERPNext's `ModeofPayment` controller. Mismatch raises `ImportError: <doctype>` on every save.
17. **`bench migrate` orphan-deletes new doctype rows when the doctype-walk runs before pull.** When adding a new doctype on a fresh deploy, `migrate` may detect it as an "orphan" and delete the `tabDocType` row even though the JSON exists on disk. Re-run `bench --site <s> execute frappe.reload_doc --kwargs '{"module":"Rmax Custom","dt":"doctype","dn":"<dn_snake>","force":1}'` to recreate the row. Symptom: MySQL table exists (`tab<DocType>`) but `SELECT name FROM tabDocType` shows no row.
18. **UAT Custom Field installation requires `bench execute frappe.utils.fixtures.sync_fixtures`.** UAT migrate is blocked by the v11 ERPNext patch, so the fixture-sync step that normally adds Custom Field rows + the underlying MySQL columns never runs. Symptoms: "Field not permitted in query: <fieldname>" on filter widgets, `Unknown column 'custom_*' in 'SET'` on whitelisted endpoints. Fix: `sudo -u v15 bench --site rmax-uat2.enfonoerp.com execute frappe.utils.fixtures.sync_fixtures`.
19. **Adding a Branch User dashboard tile is two-file change.** `rmax_dashboard.js` adds the `action_card`; `branch_user_restrict.js` whitelist must include the destination doctype too, otherwise restricted users get redirected back to rmax-dashboard the moment they click.
20. **Quotation / Delivery Note open errors for Branch Users** are usually the global `set_warehouse` default ("Stores") triggering User Permission rejection. Fix is `ignore_user_permissions=1` Property Setters on header `set_warehouse` and item `warehouse` / `target_warehouse`. List filtering (owner-only / branch warehouse) still works because it's enforced at `permission_query_conditions`.

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
