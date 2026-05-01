# Clear Light Company — Production Go-Live Checklist

Tracker for `rmax.enfonoerp.com` (SaaS Server 1, `161.97.130.108`).
Tick boxes as items land.

---

## Done

- [x] **D0** App install: `rmax_custom` on bench + on `rmax.enfonoerp.com` site
- [x] **D0** Company swap: placeholder `Clear Test` → `Clear Light Company` (abbr `CL`, country Saudi Arabia, currency SAR)
- [x] **D0** 15 Branches with `custom_doc_prefix` (HO + 14 leaves)
- [x] **D0** Cost Center tree: `Head Office - CL` (group) → 14 leaves + `Branches - CL` subgroup of 9 sales-side leaves
- [x] **D0** Warehouse tree: same shape as CC, plus `Damage - CL` subgroup with `Damage Jeddah - CL` + `Damage Riyadh - CL`
- [x] **D0** 15 Branch Configuration records
- [x] **D0** Naming-series options appended to SI / Quote / DN / PI / PR / PE / MR / SE
- [x] **D0** `Branch.custom_doc_prefix` Custom Field
- [x] **D0** Naming-series `before_insert` auto-pick hook
- [x] **D0** Stock Settings: valuation_method = Moving Average
- [x] **D0** BNPL accounts: `Tabby Clearing - CL`, `Tamara Clearing - CL`, `BNPL Fee Expense - CL`
- [x] **D0** Inter-Branch foundation: 2 group + 30 Due-from/to leaf accounts
- [x] **D0** No VAT Sale accounts: `Current Account - Naseef (N) - CL`, `Damage Written Off (N) - CL`
- [x] **D0** Company custom fields linked: bnpl_fee, novat_naseef, novat_cogs, damage_loss
- [x] **D0** Custom DocPerms: Branch User 44, Stock User 40, Damage User 21
- [x] **D0** Roles: Branch User, Stock User, Damage User
- [x] **D0** Mode of Payment seed: Cash + 6 Bank types (with ZATCA codes)
- [x] **D0** Mode of Payment Account row for `Cash` linked to `1110 - Cash - CL`
- [x] **D0** LCV Charge Template: `Standard Import KSA` (default)
- [x] **D0** HR Salary Structure: `RMAX Sponsorship KSA - CL` (Draft)
- [x] **D0** Print Formats: RMAX Tax Invoice, Quotation, Delivery Note, Purchase Order
- [x] **D0** Sales Tax: `KSA VAT 15% - CL` template + `VAT Output 15% - CL` account
- [x] **D0** Purchase Tax: `KSA VAT 15% Input - CL` template + `VAT Input 15% - CL` account

---

## Pending — YOU (Dev / Implementation Lead)

| # | Task | Status | Notes |
|---|------|--------|-------|
| D1 | Resolve frappe-erpnext-expert audit findings (CRITICAL fixed; HIGH 5-17 open) | 🔴 in progress | See `docs/prod-audit-findings.md` |
| D2 | Damage Jeddah / Damage Riyadh → Branch Configuration mapping | ⬜ | Without this, cross-branch→damage SE skips companion JE silently |
| D3 | Set `Company.custom_inter_branch_cut_over_date` on go-live day | ⬜ | Auto-injector OFF until set |
| D4 | Set `Company.custom_inter_branch_bridge_branch = Head Office` | ⬜ | Required for 3+ branch JEs |
| D5 | Tabby + Tamara Mode of Payment records | ⬜ | `custom_surcharge_percentage = 8.6957`, `custom_bnpl_clearing_account`, MoP Account row |
| D6 | Add bank GL leaves under `1200 - Bank Accounts - CL` | ⬜ | Per real bank account (HSBC, SABB, etc.) |
| D7 | Mode of Payment Account rows for Bank MoPs | ⬜ | Each Bank MoP → matching `<Bank> - CL` per company |
| D8 | Branch Configuration `mode_of_payment` allowlist per branch | ⬜ | 15 branches × select MoPs |
| D9 | Add Users to Branch Configuration `user` table | ⬜ | Roles auto-assigned |
| D10 | LCV expense charge accounts (only 5/11 created) | ⬜ | Investigate why 6 missing; rerun `lcv_template.setup_lcv_defaults()` |
| D11 | Custom domain CNAME → bench add-domain → caddy SSL | ⬜ | Awaits client DNS |
| D12 | Verify Inter Company Branch master | ⬜ | Empty currently — populate when 2nd company onboards |
| D13 | sf_trading install when 2nd Company added | ⬜ | Required for inter-company auto-PI |
| D14 | UAT migrate-blocker fix | ⬜ | Long term: fix v11 ERPNext patch or ERPNext upgrade |
| D15 | Print format smoke test on prod | ⬜ | Open SI / Quote / DN / PO; verify render |
| D16 | Branch User dashboard verify on prod | ⬜ | Login as test branch user; click each tile |
| D17 | Operator handover doc + login credentials | ⬜ | 1-page cheat sheet |
| D18 | Audit HIGH #11 — Stock Entry permission_query_conditions | ⬜ | Cross-branch leakage in list view |
| D19 | Audit HIGH #12 — SI / PI / PR ignore_user_permissions Property Setters | ⬜ | Branch users can't open cross-branch warehouse refs |
| D20 | Audit HIGH #5-#17 (remaining) | ⬜ | See findings doc |

---

## Pending — CLIENT (Accounts / Operator / Owner)

| # | Task | Status | Notes |
|---|------|--------|-------|
| C1 | Confirm chart-of-accounts opening balances | ⬜ | Load opening JE before first txn |
| C2 | Confirm Fiscal Year + Fiscal Period start/end | ⬜ | Verify Settings → Fiscal Year |
| C3 | Customer master import | ⬜ | Internal customers + B2B + B2C |
| C4 | Supplier master import | ⬜ | |
| C5 | Item master import | ⬜ | code, name, group, UOM, default warehouse, sales/purchase rate, valuation rate |
| C6 | Item Price import | ⬜ | No VAT Price + Inter Company Price + Standard Selling |
| C7 | POS Profile per branch | ⬜ | Cash drawer, default warehouse, default MoP, write-off CC |
| C8 | Confirm bank GL accounts + naming convention | ⬜ | Drives D6 |
| C9 | Confirm payment-mode list per branch | ⬜ | Drives D8 |
| C10 | Verify VAT registration number on Company | ⬜ | KSA TRN |
| C11 | ZATCA Phase 2 onboarding | ⬜ | CSR → portal → certificate (separate ksa_compliance flow) |
| C12 | Email + SMTP setup | ⬜ | Required for No VAT Sale approval emails, MR / ST notifications |
| C13 | Default printer + paper size per branch | ⬜ | |
| C14 | Logo + Letter Head | ⬜ | Upload + link to print formats |
| C15 | Tax exemption / zero-rate templates | ⬜ | If exports / exempt items |
| C16 | Roles + permissions sign-off | ⬜ | Test users — verify Branch User isolation |
| C17 | Damage Loss Account confirmation | ⬜ | Currently `Damage Written Off (N) - CL` — same as NVS COGS; finance may want separate |
| C18 | Damage warehouse policy (per-city vs centralised) | ⬜ | Drives D2 mapping |
| C19 | Workflow approvers per doctype | ⬜ | Stock Transfer, NVS — confirm assignments |
| C20 | Custom domain DNS record | ⬜ | Triggers D11 |
| C21 | Production go-live date | ⬜ | Triggers D3 |
| C22 | Backup policy (offsite copy if wanted) | ⬜ | SaaS already backs up |
| C23 | User training | ⬜ | Walk through user-guide.html |

---

## Server reference

| Site | Server | Server ID | Bench path | User |
|------|--------|-----------|------------|------|
| **rmax.enfonoerp.com** (PROD) | SaaS Server 1 (161.97.130.108) | `3c312733-e6ea-4d4a-8fa1-5354f0e23732` | `/home/frappe/frappe-bench` | `frappe` |
| rmax-uat2.enfonoerp.com | AQRAR (185.193.19.184) | `3beb2d91-86d1-4d2d-ba0b-30955992455c` | `/home/v15/frappe-bench` | `v15` |
| rmax_dev2 | RMAX (5.189.131.148) | `41ef79dc-a2fd-418a-bd88-b5f5173aeaf7` | `/home/v15/frappe-bench` | `v15` |
