# RMAX Custom — Agent Context

> **This file contains everything an AI agent needs to continue working on this project.**

## Project Overview

RMAX Custom is a Frappe/ERPNext v15 custom app for RMAX's multi-branch trading/distribution business in Saudi Arabia. It extends ERPNext with branch-based access control, POS payment flows, inter-company automation, stock transfer workflows, and Material Request enhancements.

**Site:** rmax_dev2 on RMAX Server (5.189.131.148)
**URL:** rmax-dev.fateherp.com
**Repo:** github.com/EnfonoTech/RMAX-Custom (branch: main)
**Docs:** https://rmax-docs.vercel.app
**Docs source:** /Users/sayanthns/Documents/RMAX/rmax-docs/

---

## Server Connection

```bash
# Get API secret
ssh root@207.180.209.80 "grep AGENT_SECRET /opt/server-manager-agent/.env"
# Secret: 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3

# Server ID for RMAX
# 41ef79dc-a2fd-418a-bd88-b5f5173aeaf7

# Run command on server
curl -s -X POST \
  -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command": "your command here"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command

# Git remote on server is "upstream" not "origin"
# Pull: git pull upstream main
# Bench user: v15, path: /home/v15/frappe-bench
# Site: rmax_dev2

# Deploy sequence:
# 1. git push origin main (local)
# 2. git pull upstream main (server)
# 3. bench --site rmax_dev2 migrate (if schema/fixture changes)
# 4. bench --site rmax_dev2 clear-cache
# 5. sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web
# bench build is blocked by maintenance window (2-5 AM IST)
```

---

## Architecture

### Key Files

| File | Purpose |
|------|---------|
| `hooks.py` | All app config: JS includes, doc_events, permission_query_conditions, fixtures, after_migrate |
| `setup.py` | after_migrate hook: creates Custom DocPerm for Branch User role (25 DocTypes) |
| `branch_defaults.py` | before_validate hook: overrides cost center on SI/PI/PE/DN/PR for branch users |
| `branch_filters.py` | permission_query_conditions: filters list views by branch warehouses |
| `inter_company.py` | on_submit hook: auto-creates Purchase Invoice from inter-company Sales Invoice |
| `branch_configuration.py` | Core: auto-manages User Permissions, role assignment, company default CC |
| `stock_transfer.py` | Workflow validation: branch-based approval, self-approval prevention |
| `material_request.py` | APIs: can_create_stock_transfer, create_stock_transfer_from_mr |
| `material_request_doctype.js` | doctype_js: hide standard buttons, add Stock Transfer button |
| `warehouse_pick_list.py` | Warehouse Pick List: get_pending_items API, mark_completed |
| `warehouse_pick_list.js` | Get Items button, available qty color-coding, urgent highlights |

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

1. **bench build required** for `app_include_js` and `app_include_css` changes. Use `doctype_js` for immediate effect.
2. **async:false deprecated** in browsers — always use async `frappe.call` with callback.
3. **frappe.client.get_count on User Permission** fails for non-admin users — use whitelisted API instead.
4. **user_doc.add_roles()** can fail silently during Branch Config save — use direct `Has Role` insert.
5. **Property Setter fixtures** need BOTH: correct entry in JSON AND name in hooks filter list.
6. **Duplicate default User Permission** — Frappe allows only ONE is_default per allow type per user. Check before setting.
7. **Rogue warehouse permissions** — old code in ST before_save auto-created WH permissions. REMOVED. Only Branch Config manages permissions now.
8. **ERPNext role name** is "Stock User" not "Warehouse User".

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

---

## Documentation

- **User docs:** https://rmax-docs.vercel.app (source: /Users/sayanthns/Documents/RMAX/rmax-docs/)
- **Developer docs:** DOCUMENTATION.md in repo root
- **User guide HTML:** rmax_custom/public/html/user-guide.html (accessible from site)
