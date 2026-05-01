# RMAX Custom App - Complete Documentation

> **App Name:** rmax_custom  
> **Publisher:** Enfono  
> **License:** MIT  
> **Framework:** Frappe v15 + ERPNext  
> **Dev site:** rmax_dev2 on RMAX Server (5.189.131.148)  
> **UAT site:** rmax-uat2.enfonoerp.com on AQRAR Server (185.193.19.184)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Custom DocTypes](#2-custom-doctypes)
3. [Custom Fields & Property Setters](#3-custom-fields--property-setters)
4. [Workflows](#4-workflows)
5. [Server-Side Logic (Python)](#5-server-side-logic-python)
6. [Client-Side Logic (JavaScript)](#6-client-side-logic-javascript)
7. [API Endpoints](#7-api-endpoints)
8. [Hooks Configuration](#8-hooks-configuration)
9. [Fixtures](#9-fixtures)
10. [Architecture Diagram](#10-architecture-diagram)
11. [Session 2026-04-22 Additions](#11-session-2026-04-22-additions)

---

## 1. Overview

RMAX Custom is a Frappe/ERPNext custom app built for RMAX's trading and distribution business. It extends ERPNext with:

- **POS-style Sales Invoice workflow** with payment popup and multi-mode payments
- **Inter-company transaction automation** (auto-create Purchase Invoice from Sales Invoice)
- **Branch-based access control** with automatic user permission management
- **Stock Transfer workflow** with approval states
- **Landed Cost Voucher enhancement** with CBM-based distribution
- **LCV Charge Template + Purchase Receipt checklist** — reusable charge list, auto-ticked after LCV submission, with dashboard status indicator
- **Customer creation directly from Sales Invoice** including a Sales-Manager-gated VAT duplicate override
- **Bulk Purchase Invoice creation** from multiple Purchase Receipts
- **Final GRN (Goods Received Note)** replacement flow
- **VAT and contact validation** rules (Saudi Arabia compliance)
- **Warehouse stock visibility** popup on item selection
- **Damage workflow** (Damage Slip → Damage Transfer → Stock Entry / Write-off) with role-gated access
- **HR defaults** — Sponsorship / Non-Sponsorship Employee Grades, KSA salary components, shipped Sponsorship salary structure per company
- **Dashboard restrictions** — branch / stock / damage users land on `rmax-dashboard` with a restricted module profile

---

## 2. Custom DocTypes

### 2.1 Branch Configuration

| Field | Type | Description |
|-------|------|-------------|
| `branch` | Link → Branch | The branch this config belongs to (autoname) |
| `company` | Link → Company | Company the branch belongs to |
| `mode_of_payment` | Table → Branch Configuration Mode of Payment | Cash + Bank Modes of Payment allowed for this branch (Sales Invoice constraint) |
| `user` | Table → Branch Configuration User | Users assigned to this branch |
| `warehouse` | Table → Branch Configuration Warehouse | Warehouses for this branch |
| `cost_center` | Table → Branch Configuration Cost Center | Cost centers for this branch |

**Behavior:**
- On save, automatically creates `User Permission` records for each user, granting access to the branch, its warehouses, and cost centers.
- On user removal, automatically deletes the corresponding `User Permission` records.
- Permissions are set with `apply_to_all_doctypes = 1`.

**Child Tables:**
- **Branch Configuration User** — fields: `user` (Link → User), `role` (Select)
- **Branch Configuration Warehouse** — fields: `warehouse` (Link → Warehouse)
- **Branch Configuration Cost Center** — fields: `cost_center` (Link → Cost Center)
- **Branch Configuration Mode of Payment** (`istable=1`) — fields: `mode_of_payment` (Link → Mode of Payment, filtered to type=Cash/Bank), `type` (Data, fetched from `mode_of_payment.type`, read-only)

**Sales Invoice integration (Branch Users only):**

When a Branch User saves an SI, `branch_defaults.override_payment_accounts_from_branch` (before_validate) walks `payments[*]`:

| Row state | Action |
|-----------|--------|
| MoP type=Cash, MoP listed in branch | keep MoP, resync `account` from `Mode of Payment Account` for SI company |
| MoP type=Cash, MoP NOT listed, branch HAS cash MoPs | swap to first cash MoP in branch list, resync account |
| MoP type=Cash, branch has zero cash MoPs configured | drop the row |
| Same for type=Bank | as above |
| All other types (BNPL/General/Phone) | untouched |

Opt-out: if the branch has zero Cash AND zero Bank rows in the table, the hook is a no-op (legacy fallback).

Bypass roles: System Manager, Sales Manager, Sales Master Manager, Stock Manager, Administrator.

The matching POS popup endpoint `rmax_custom.api.sales_invoice_payment.get_payment_modes_with_account` applies the same filter to the dropdown so Branch Users only see allowed Cash/Bank MoPs alongside all enabled BNPL/General/Phone MoPs.

---

### 2.2 Inter Company Branch

| Field | Type | Description |
|-------|------|-------------|
| `branch_name` | Data | Name of the inter-company branch |
| `company_cost_centers` | Table → Inter Company Branch Cost Center | Company-specific cost centers & warehouses |

**Behavior:**
- Validates that no duplicate company entries exist in the child table.
- Provides a search helper (`get_branches_for_company`) that returns branches configured for a specific company.

**Child Table — Inter Company Branch Cost Center:**

| Field | Type | Description |
|-------|------|-------------|
| `company` | Link → Company | The company this row applies to |
| `cost_center` | Link → Cost Center | Default cost center for this company |
| `warehouse` | Link → Warehouse | Default warehouse for this company |

---

### 2.3 No VAT Sale (`No VAT Sale`)

Submittable doctype that books a non-VAT-able cash sale. On submit it posts a Journal Entry (cash receipt) + Stock Entry (Material Issue against `Damage Written Off (N)`).

| Field | Type | Notes |
|-------|------|-------|
| `branch` | Link → Branch | Selects which Branch Configuration drives the warehouse filter |
| `company` | Link → Company | |
| `warehouse` | Link → Warehouse | Filtered to warehouses listed in `Branch Configuration Warehouse` for the chosen branch (server + JS guard) |
| `customer_name` | Data | Walk-in customer name (no Customer record created) |
| `mode_of_payment` | Link → Mode of Payment | Drives `cash_account` prefill |
| `naseef_account` / `cogs_account` / `cash_account` | Link → Account | Auto-prefilled per company defaults |
| `items` | Table → No VAT Sale Item | `item_code, qty, rate, amount, valuation_rate, cost_amount` |
| `total_selling_value` / `total_cost_value` | Currency | Computed |
| `approval_status` | Select | Draft / Pending Approval / Approved / Rejected (read-only on form) |
| `approved_by` | Link → User | Required to send for approval |
| `approval_remarks` | Small Text | Free text — set on Approve / Reject |
| `journal_entry` / `stock_entry` | Link (read-only) | Backlinks created on submit |

**Permissions (post Apr-2026)**
- Standard DocPerm in `no_vat_sale.json` keeps only `System Manager` + `Sales Manager`.
- `setup.restrict_no_vat_sale_to_sales_manager()` runs every `after_migrate` and deletes leftover Custom DocPerm rows on the doctype (cleanup of older deploys with Branch User / Stock User / Sales User / Accounts Manager).
- `branch_filters.no_vat_sale_permission_query` bypasses for Sales Manager + System Manager.

**Approval workflow (desk only — no PWA yet)**
- `before_insert` forces `approval_status = "Draft"`.
- `before_submit` blocks submit if status ≠ Approved (defends against direct `frappe.client.submit`).
- `on_update` notifies `approved_by` via `frappe.desk.form.assign_to.add` (ToDo + email; falls back to manual ToDo + `frappe.sendmail`) when status flips to Pending Approval.
- `on_submit` closes any open ToDos for the doc.

**Whitelisted APIs (`rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale`)**
- `submit_for_approval(name)` — Draft → Pending Approval; throws if `approved_by` empty.
- `approve_no_vat_sale(name, remarks)` — verifies caller is the named approver (or Sales Manager / System Manager), sets status=Approved, calls `submit()` with `flags.ignore_permissions = True`.
- `reject_no_vat_sale(name, remarks)` — sets status=Rejected, keeps Draft, closes open ToDos.
- `get_branch_warehouses(branch)` — returns the branch's warehouse allowlist; powers `set_query` on `warehouse` and the server-side `_validate_branch_warehouse_match` guard.

**Form UI (`no_vat_sale.js`)**
- Status indicator pill (Draft grey / Pending orange / Approved green / Rejected red).
- Buttons under "Approval" group:
  - `Send for Approval` (creator, Draft / Rejected) → `submit_for_approval`.
  - `Approve & Submit` (named approver, Pending Approval) → `approve_no_vat_sale` with optional remarks.
  - `Reject` (named approver, Pending Approval) → `reject_no_vat_sale` with mandatory reason.
- Branch change resets `warehouse` if the existing pick falls out of scope.

---

### 2.4 Stock Transfer

| Field | Type | Description |
|-------|------|-------------|
| `company` | Link → Company | Company |
| `set_source_warehouse` | Link → Warehouse | Source warehouse |
| `set_target_warehouse` | Link → Warehouse | Target warehouse |
| `items` | Table → Stock Transfer Item | Items to transfer |
| `stock_entry` | Link → Stock Entry | Auto-created Stock Entry (read-only) |
| `stock_entry_created` | Check | Flag indicating SE was created |

**Behavior:**
- Subject to **Stock Transfer Workflow** (Draft → Pending → Approved/Rejected).
- On submit (when `workflow_state == "Approved"`), automatically creates and submits a **Stock Entry** of type "Material Transfer".
- Source warehouse defaults to the user's default warehouse permission.
- Target warehouse filter excludes the source warehouse.
- Before save, ensures the user has `User Permission` for the target warehouse (auto-creates if missing).

**Child Table — Stock Transfer Item:**

| Field | Type | Description |
|-------|------|-------------|
| `item_code` | Link → Item | Item |
| `item_name` | Data | Item name (fetched) |
| `quantity` | Float | Quantity to transfer |
| `uom` | Link → UOM | Unit of measure |
| `uom_conversion_factor` | Float | Conversion factor (fetched via API) |

---

## 3. Custom Fields & Property Setters

### 3.1 Custom Fields

| DocType | Field Name | Type | Label | Purpose |
|---------|-----------|------|-------|---------|
| Customer | `custom_vat_registration_number` | Data | VAT Registration Number | Saudi VAT number (15 digits) |
| Sales Invoice | `custom_payment_mode` | Select | Payment Mode | Options: Cash, Credit — drives POS popup behavior |
| Sales Invoice | `custom_inter_company_branch` | Link → Inter Company Branch | Inter Company Branch | Determines cost center/warehouse for auto-created PI |
| Quotation | `custom_payment_mode` | Select | Payment Mode | Payment mode on quotation |
| Landed Cost Voucher | `custom_distribute_by_cbm` | Check | Distribute by CBM | Enables CBM-ratio charge distribution |
| Landed Cost Item | `custom_cbm` | Float | CBM | Cubic meter value per item line |

(See section 2.3 for No VAT Sale schema fields including `approval_status`, `approved_by`, `approval_remarks`.)

### 3.2 Property Setters

| DocType | Field | Property | Value | Purpose |
|---------|-------|----------|-------|---------|
| Material Request | `material_request_type` | default | Material Transfer | Default MR type is transfer |
| Material Request | `schedule_date` | hidden | 1 | Hide header schedule date |
| Material Request Item | `schedule_date` | hidden | 1 | Hide per-item schedule date |
| Material Request Item | `schedule_date` | default | Today | Auto-set to today |
| Material Request Item | `schedule_date` | reqd | 0 | Not mandatory |
| Material Request Item | `from_warehouse` | hidden | 1 | Simplify transfer UI |
| Material Request Item | `warehouse` | hidden | 1 | Simplify transfer UI |
| Landed Cost Item | `qty` | columns | 1 | Show qty in grid |
| Customer | `customer_type` | options | Company\nIndividual\nPartnership\nBranch | Added "Branch" type |
| Quotation | `set_warehouse` | ignore_user_permissions | 1 | Branch User can open quotes referencing global default "Stores" |
| Quotation Item | `warehouse` | ignore_user_permissions | 1 | Same as above for per-item warehouse |
| Delivery Note | `set_warehouse` | ignore_user_permissions | 1 | Branch User can open DNs with cross-branch source warehouse |
| Delivery Note Item | `warehouse` | ignore_user_permissions | 1 | Same for per-item warehouse |
| Delivery Note Item | `target_warehouse` | ignore_user_permissions | 1 | Same for per-item target warehouse |

---

## 4. Workflows

### Stock Transfer Workflow

| State | Doc Status | Allow Edit | Update Field |
|-------|-----------|------------|--------------|
| Draft | 0 | All | workflow_state |
| Pending | 0 | All | workflow_state |
| Approved | 1 | Specific roles | workflow_state |
| Rejected | 0 | Specific roles | workflow_state |

**Transitions:** Draft → Pending → Approved/Rejected

When approved and submitted, the Stock Transfer auto-creates a Stock Entry.

---

## 5. Server-Side Logic (Python)

### 5.1 Inter-Company Auto PI Creation (`inter_company.py`)

**Trigger:** `Sales Invoice → on_submit` (via doc_events hook)

**Flow:**
1. Checks if the Sales Invoice has `is_internal_customer` and `represents_company`.
2. Checks no duplicate PI already exists.
3. Calls ERPNext's `make_inter_company_purchase_invoice()`.
4. Uses patches from `sf_trading` to bypass session/default warehouse interference.
5. Sets `bill_no` and `bill_date` from the Sales Invoice.
6. Handles **return invoices** — links to the original PI and sets `is_return = 1`.
7. Applies **branch-specific cost center and warehouse** from `Inter Company Branch` configuration.
8. Validates warehouse belongs to the buying company (prevents cross-company mismatch).
9. Fetches and applies the **default Purchase Taxes and Charges Template**.
10. Strips invalid session defaults (warehouse/cost center from wrong company).
11. Inserts the PI as draft with `ignore_permissions=True`.

**Key helper functions:**
- `_get_branch_data(doc, buying_company)` — Fetches cost center/warehouse from Inter Company Branch config
- `_apply_default_purchase_taxes(pi, branch_data)` — Applies default tax template
- `_clear_invalid_session_defaults(pi)` — Removes cross-company values
- `_warehouse_belongs_to_company(warehouse, company)` — Validates warehouse ownership
- `_cost_center_belongs_to_company(cost_center, company)` — Validates cost center ownership

### 5.2 Landed Cost Voucher Override (`overrides/landed_cost_voucher.py`)

**Overrides:** `erpnext.stock.doctype.landed_cost_voucher.landed_cost_voucher.LandedCostVoucher`

**Enhancements:**
- **CBM Distribution:** When `distribute_charges_based_on == "Distribute Manually"` AND `custom_distribute_by_cbm` is checked, distributes charges proportionally based on each item's `custom_cbm` value.
- **Standard Distribution:** For Qty or Amount-based distribution, uses the same ratio logic as ERPNext but with rounding correction on the last item.
- **Validation:** Enforces single tax row when using "Distribute Manually" mode.

### 5.3 Branch Configuration (`branch_configuration.py`)

**Auto-permission management:**
- `on_update`: Creates `User Permission` records for each user × branch/warehouse/cost_center combination.
- `before_save`: Detects removed users and deletes their permissions.

### 5.4 Stock Transfer (`stock_transfer.py`)

- `on_submit`: Creates and submits a Stock Entry (Material Transfer) when workflow state is "Approved".
- `get_item_uom_conversion`: Whitelisted API to fetch UOM conversion factors.

---

## 6. Client-Side Logic (JavaScript)

### 6.1 Sales Invoice Popup (`sales_invoice_popup.js`)

**Features:**
- Adds "New Invoice" button to open a new Sales Invoice in a new tab.
- Forces `update_stock = 1` when POS Profile is selected.
- Handles `custom_payment_mode`:
  - **Cash**: No auto POS behavior (uses payment popup instead).
  - **Credit**: Disables POS mode; filters customers to those with credit limits.
- **Enter key navigation**: Moves focus across item grid columns and rows; auto-adds new row at end.
- **Stock check**: On item add, item_code change, or qty change, checks warehouse stock balance and caps qty if insufficient.

### 6.2 POS Payment Popup (`sales_invoice_pos_total_popup.js`)

**The core POS workflow for Cash mode:**

1. **Intercepts Submit**: When user clicks Submit on a Cash Sales Invoice, shows a payment dialog BEFORE submit.
2. **Payment Modes Loading**: Fetches from POS Profile or falls back to all enabled `Mode of Payment` with company accounts.
3. **Dialog UI**: Shows invoice total + one Currency field per payment mode + "fill" buttons to auto-allocate.
4. **Click-to-fill**: Clicking a payment input auto-fills the remaining balance.
5. **Save & Submit**: Updates payment amounts on the form, saves, submits, then creates **Payment Entry** records via `create_pos_payments_for_invoice` API.
6. **Save only**: Updates payments and saves without submitting.
7. **Credit mode**: Shows a confirm dialog asking whether to submit immediately.

### 6.3 Create Customer (`create_customer.js`)

- Adds a "Create New Customer" button above the customer field on Sales Invoice.
- Opens a dialog with fields: Customer Name, Mobile No, Email, VAT Registration Number, and full Address details.
- Address fields become mandatory when VAT number is provided (Saudi compliance).
- Calls `create_customer_with_address` API and auto-sets the new customer on the invoice.

### 6.4 Warehouse Stock Popup (`warehouse_stock_popup.js`)

- When an item is selected in the items grid (Sales Invoice, Quotation, etc.), shows a panel below the grid displaying stock quantities across all company warehouses.
- Highlights the currently selected warehouse.
- Click a warehouse row to set it on the item.
- Shows top 5 warehouses by default; "Show All" loads the complete list.
- Auto-hides when no item is selected.

### 6.5 Create Multiple Suppliers (`create_multiple_supplier.js`)

- Adds "Add Multiple Suppliers" button on Item form.
- Opens a dialog with a table of Supplier links.
- Creates `Party Specific Item` records linking each supplier to the item.

### 6.6 Material Request (`materiel_request.js`)

- Auto-sets `set_warehouse` (target) from the user's default warehouse permission.
- Filters `set_from_warehouse` to exclude the target warehouse and match the company.
- Ignores user permissions on the target warehouse filter.

### 6.7 VAT Validation (`vat_validation.js`)

- On Customer form, restricts `custom_vat_registration_number` to digits only, max 15.
- On validate, enforces exactly 15 digits for VAT and checks uniqueness via API.
- Validates phone numbers have at least 10 digits.
- Hides "Branch" from `customer_type` options for non-System Manager/Auditor users.

### 6.8 Contact Validation (`contact_validation.js`)

- Validates all phone numbers in the Contact's `phone_nos` table have at least 10 digits.

### 6.9 Purchase Receipt - Final GRN (`purchase receipt.js`)

- Adds "Final GRN" button under "Create" menu on Purchase Receipt.
- Copies all header fields, items, and taxes to a new Purchase Receipt.
- Sets posting time to 10 minutes before the original (for ordering).
- On submit of the new receipt, **auto-cancels** the original (if submitted) or **auto-deletes** it (if draft).

### 6.10 Purchase Receipt List (`purchase_receipt_list.js`)

- Adds "Create Single Purchase Invoice" action to list view.
- Allows selecting multiple Purchase Receipts and creating one consolidated Purchase Invoice.

### 6.11 Landed Cost Voucher (`landed_cost_voucher.js`)

- Client-side companion to the Python override.
- When "Distribute by CBM" is checked with "Distribute Manually", auto-distributes charges by `custom_cbm` ratio.
- Recalculates on CBM value change or tax amount change.
- Patches the form controller's `set_applicable_charges_for_item` method.

### 6.12 Quotation Custom Script (`quotation.js`)

- Adds "Sales Invoice" button under "Create" menu on submitted Quotations.
- Calls ERPNext's `make_sales_invoice` mapper.

---

## 7. API Endpoints

### 7.1 Customer APIs (`api/customer.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.api.customer.create_customer_with_address` | Whitelisted | Creates a Customer + Address in one call. Sets defaults from user permissions and company. |
| `rmax_custom.api.customer.validate_vat_customer` | Whitelisted | Checks VAT uniqueness across customers (skips "Branch" type). |
| `rmax_custom.api.customer.validate_phone_numbers` | Whitelisted | Validates mobile/phone have 10+ digits. |

### 7.2 Sales Invoice Payment APIs (`api/sales_invoice_payment.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.api.sales_invoice_payment.get_payment_modes_with_account` | Whitelisted | Returns enabled Mode of Payment names that have a default account for the company. Optionally filters by a provided list (from POS Profile). For Branch Users (no override role), Cash + Bank type MoPs are restricted to the user's `Branch Configuration Mode of Payment` allowlist; BNPL / General / Phone pass through. Branches with zero Cash+Bank rows opt out (no filter). |
| `rmax_custom.api.sales_invoice_payment.create_pos_payments_for_invoice` | Whitelisted | Creates and submits Payment Entry records for a submitted Sales Invoice. One PE per mode of payment. Validates outstanding amounts. |

### 7.3 Warehouse Stock API (`api/warehouse_stock.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.api.warehouse_stock.get_item_warehouse_stock` | Whitelisted | Returns stock balance across all warehouses using the Bin table (optimized). Supports target warehouse prioritization and pagination. |

### 7.4 Material Request API (`api/material_request.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.api.material_request.create_material_request` | Whitelisted | Creates and submits a Material Request for Material Transfer. Validates item, warehouses, and quantity. |

### 7.5 Purchase Invoice API (`api/purchase_invoice.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.api.purchase_invoice.create_single_purchase_invoice` | Whitelisted | Creates one Purchase Invoice from multiple Purchase Receipts. Links items back to their source receipts. |

### 7.6 Item API (`api/item.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.api.item.create_party_specific_items` | Whitelisted | Creates Party Specific Item records linking multiple suppliers to an item. Prevents duplicates. |

### 7.7 Stock Transfer API (`stock_transfer.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.rmax_custom.doctype.stock_transfer.stock_transfer.get_item_uom_conversion` | Whitelisted | Returns UOM conversion factor for an item. |

### 7.8 No VAT Sale APIs (`rmax_custom/doctype/no_vat_sale/no_vat_sale.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_branch_warehouses` | Whitelisted | Returns the Warehouse names listed under a given Branch's `Branch Configuration Warehouse` child table. Powers the warehouse `set_query` and the server-side `_validate_branch_warehouse_match` guard. |
| `rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.submit_for_approval` | Whitelisted | Draft → Pending Approval. Throws if `approved_by` is empty. Triggers ToDo + email assignment via `frappe.desk.form.assign_to.add`. |
| `rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.approve_no_vat_sale` | Whitelisted | Verifies caller is the named approver (or Sales/System Manager); sets status=Approved; calls `submit()` with `flags.ignore_permissions=True` (role gate already passed). Optional remarks. |
| `rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.reject_no_vat_sale` | Whitelisted | Verifies approver, sets status=Rejected, keeps Draft, closes any open ToDos. |
| `rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_default_accounts` | Whitelisted | Returns `{naseef_account, cogs_account, cash_account}` from Company defaults + Mode of Payment Account. |
| `rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_item_rate` | Whitelisted | Returns the No VAT Price list rate for an item. |
| `rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_item_valuation` | Whitelisted | Returns the warehouse-specific valuation rate from `Bin` (falls back to Item.valuation_rate). |

### 7.9 Branch Defaults APIs (`branch_defaults.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `rmax_custom.branch_defaults.get_user_branch_accounts` | Whitelisted | Returns `{branch, cash:[{mop, account}, …], bank:[{mop, account}, …]}` for the user's resolved Branch Configuration. Account values are derived from `Mode of Payment Account` for the SI's company. Used by `sales_invoice_doctype.js` to constrain payment rows on `mode_of_payment` change and `before_save`. |

---

## 8. Hooks Configuration

```python
# Global JS includes (loaded on every desk page)
app_include_js = [
    "warehouse_stock_popup.js",       # Stock display panel
    "sales_invoice_pos_total_popup.js", # POS payment popup
    "sales_invoice_popup.js",          # SI enhancements
    "create_customer.js",              # Quick customer creation
    "create_multiple_supplier.js",     # Bulk supplier linking
    "materiel_request.js",             # MR defaults
    "vat_validation.js",               # Customer VAT rules
    "contact_validation.js",           # Contact phone rules
]

# DocType-specific JS
doctype_js = {
    "Quotation": "quotation.js",           # Create SI button
    "Purchase Receipt": "purchase receipt.js",  # Final GRN
    "Landed Cost Voucher": "landed_cost_voucher.js",  # CBM distribution
}

# List view JS
doctype_list_js = {
    "Purchase Receipt": "purchase_receipt_list.js",  # Bulk PI creation
}

# DocType class override
override_doctype_class = {
    "Landed Cost Voucher": "rmax_custom.overrides.landed_cost_voucher.LandedCostVoucher"
}

# Document events (excerpt — full list in hooks.py)
doc_events = {
    "Sales Invoice": {
        "before_validate": [
            "rmax_custom.branch_defaults.override_cost_center_from_branch",
            "rmax_custom.branch_defaults.override_payment_accounts_from_branch",
            "rmax_custom.bnpl_uplift.apply_bnpl_uplift",
        ],
        "validate": "rmax_custom.bnpl_uplift.validate_bnpl_uplift",
        "on_submit": "rmax_custom.inter_company.sales_invoice_on_submit",
        "on_cancel": "rmax_custom.inter_company_dn.sales_invoice_on_cancel",
    },
}

# Fixtures exported with the app
fixtures = [
    "Workflow",
    "Workflow State",
    "Workflow Action Master",
    "Custom Field" (filtered list),
    "Property Setter" (filtered list),
]
```

---

## 9. Fixtures

### Custom Fields Exported

| Name | Purpose |
|------|---------|
| `Sales Invoice-custom_payment_mode` | Cash/Credit selector |
| `Sales Invoice-custom_inter_company_branch` | Branch link for inter-company PI |
| `Sales Invoice-custom_pos_payments_json` | Long Text — captures pre-uplift POS payment snapshot for BNPL surcharge reconciliation |
| `Sales Invoice-custom_bnpl_portion_ratio` / `custom_bnpl_total_uplift` / `custom_bnpl_settled` / `custom_bnpl_settlement` | BNPL uplift bookkeeping |
| `Sales Invoice Item-total_vat_linewise` / `custom_original_rate` / `custom_bnpl_uplift_amount` | Per-line VAT + BNPL pre-uplift fields |
| `Mode of Payment-custom_surcharge_percentage` | Non-zero flags MoP as BNPL-type |
| `Mode of Payment-custom_bnpl_clearing_account` | Clearing account for BNPL receivable |
| `Quotation-custom_payment_mode` | Payment mode on quotation |
| `Quotation Item-total_vat_linewise` | Per-line VAT total |
| `Landed Cost Voucher-custom_distribute_by_cbm` | CBM distribution toggle |
| `Landed Cost Item-custom_cbm` | CBM value per item |
| `Customer-custom_vat_registration_number` / `custom_allow_duplicate_vat` / `custom_duplicate_vat_reason` | Saudi VAT number + duplicate override |
| `Purchase Receipt-custom_lcv_*` | LCV checklist machinery |
| `Delivery Note-custom_is_inter_company` / `custom_inter_company_branch` / `custom_inter_company_si` / `custom_inter_company_status` | Inter-Company DN consolidation |
| `Company-custom_novat_naseef_account` / `custom_novat_cogs_account` | No VAT Sale GL accounts |
| `Company-custom_damage_warehouse` / `custom_damage_loss_account` / `custom_bnpl_fee_account` | Damage workflow + BNPL fee posting |
| `Material Request-custom_is_urgent` / `Material Request Item-custom_is_urgent` | Urgent flag for branch dashboard |
| `Material Request Item-custom_source_available_qty` / `custom_target_available_qty` | Available qty widgets on MR form |

### Property Setters Exported

- Material Request fields simplified for transfer workflow.
- Customer type extended with "Branch".
- Landed Cost Item qty column shown.
- `ignore_user_permissions=1` on warehouse fields for: Item Default, Material Request, Material Request Item, Stock Entry, Stock Entry Detail, **Quotation, Quotation Item, Delivery Note, Delivery Note Item** (Phase 2 add-ons letting Branch Users open docs that reference cross-branch warehouses).
- Sales Invoice list-view standard filters: `grand_total`, `total_qty`, `contact_mobile`.
- Customer global search fields: `customer_name,mobile_no,custom_vat_registration_number`.

---

## 10. Architecture Diagram

```
                         RMAX Custom App
                              |
        +---------+-----------+-----------+----------+
        |         |           |           |          |
   DocTypes    Overrides   Doc Events   APIs     Client JS
        |         |           |           |          |
   Branch     Landed Cost  SI on_submit  customer   POS Payment
   Config     Voucher      (auto PI)     warehouse  Popup
        |         |                      stock      
   Inter Co   CBM-based                  payment    Create
   Branch     distribution              material    Customer
        |                               request     
   Stock                                purchase    Warehouse
   Transfer                             invoice     Stock Panel
   (workflow)                           item        
                                                    Final GRN
                                                    
                                                    VAT/Contact
                                                    Validation
```

### Data Flow: Sales Invoice Cash Payment

```
User creates Sales Invoice (Cash mode)
    → Selects items (stock check + warehouse popup)
    → Clicks Submit
    → Payment Popup appears
    → User allocates amounts across payment modes
    → Click "Save & Submit"
        → Updates SI payments table
        → Saves & Submits SI
        → Creates Payment Entry per payment mode
        → If inter-company: auto-creates draft Purchase Invoice
```

### Data Flow: Stock Transfer

```
User creates Stock Transfer
    → Source warehouse auto-set from user default
    → Selects target warehouse + items
    → Saves → workflow_state = "Draft"
    → Submits for approval → "Pending"
    → Approver approves → "Approved" → auto-creates Stock Entry
    → OR Approver rejects → "Rejected"
```

### Data Flow: Branch Configuration

```
Admin configures Branch
    → Adds users, warehouses, cost centers
    → On save: auto-creates User Permissions
    → Users see only their branch's warehouses/cost centers
    → On user removal: auto-deletes permissions
```

---

## Dependencies

- **ERPNext v15** — Core ERP functionality
- **sf_trading** — Provides `apply_patch` / `restore_patch` and `apply_defaults_patch` / `restore_defaults_patch` used in inter-company PI creation to bypass session defaults

---

## File Structure

```
rmax_custom/
├── __init__.py
├── hooks.py                          # App configuration
├── inter_company.py                  # Auto PI creation on SI submit
├── landed_cost.py                    # Helper for distribution field
├── overrides/
│   └── landed_cost_voucher.py        # LCV class override (CBM)
├── api/
│   ├── customer.py                   # Customer creation & VAT validation
│   ├── sales_invoice_payment.py      # Payment modes & PE creation
│   ├── warehouse_stock.py            # Stock balance query
│   ├── material_request.py           # MR creation
│   ├── purchase_invoice.py           # Bulk PI from Purchase Receipts
│   └── item.py                       # Party Specific Item creation
├── public/js/
│   ├── warehouse_stock_popup.js      # Stock display panel
│   ├── sales_invoice_popup.js        # SI form enhancements
│   ├── sales_invoice_pos_total_popup.js  # POS payment popup
│   ├── sales_invoice_inter_company.js    # (Inter-company SI JS)
│   ├── create_customer.js            # Quick customer dialog
│   ├── create_multiple_supplier.js   # Bulk supplier linking
│   ├── materiel_request.js           # MR defaults
│   ├── vat_validation.js             # VAT & phone rules
│   ├── contact_validation.js         # Contact phone rules
│   ├── purchase receipt.js           # Final GRN flow
│   ├── purchase_receipt_list.js      # Bulk PI list action
│   └── landed_cost_voucher.js        # CBM distribution client
├── rmax_custom/
│   ├── custom_scripts/
│   │   └── quotation/
│   │       ├── quotation.js          # Create SI from Quotation
│   │       └── quotation.py          # (empty)
│   ├── custom/                       # JSON field customizations
│   │   ├── sales_invoice.json
│   │   ├── sales_invoice_item.json
│   │   ├── quotation.json
│   │   ├── customer.json
│   │   ├── address.json
│   │   ├── packed_item.json
│   │   └── material_request_item.json
│   ├── page/
│   │   └── return_invoice/           # Return Invoice page
│   └── doctype/
│       ├── branch_configuration/     # Branch access control
│       ├── branch_configuration_user/
│       ├── branch_configuration_warehouse/
│       ├── branch_configuration_cost_center/
│       ├── inter_company_branch/     # Inter-company config
│       ├── inter_company_branch_cost_center/
│       ├── stock_transfer/           # Stock Transfer with workflow
│       └── stock_transfer_item/
├── fixtures/
│   ├── workflow.json
│   ├── workflow_state.json
│   ├── workflow_action_master.json
│   ├── custom_field.json
│   └── property_setter.json
├── templates/
│   └── pages/
├── config/
│   └── __init__.py
├── pyproject.toml
├── license.txt
└── README.md
```

---

## 11. Session 2026-04-22 Additions

### 11.1 Customer VAT Duplicate Override

**Custom Fields (permlevel = 1)**
- `custom_allow_duplicate_vat` (Check) — manager override flag.
- `custom_duplicate_vat_reason` (Small Text) — mandatory when override is on.

**Roles allowed to tick the override**: `Sales Manager`, `Sales Master Manager`, `System Manager`. Granted via `Custom DocPerm` permlevel 1 by `setup_vat_duplicate_override_perms()` in `after_migrate`.

**Enforcement layers**
1. `Customer.validate` → `rmax_custom.api.customer.enforce_vat_duplicate_rule`
2. Whitelisted APIs `validate_vat_customer` and `create_customer_with_address` re-check the role and reason.
3. `vat_validation.js` and `create_customer.js` hide the override fields for unauthorised users and forward the flag to the server.

`customer_type = "Branch"` is always exempt. VAT Registration Number must be exactly 15 digits.

### 11.2 Sales Invoice: `update_stock` Default + Branch Lock

File: `public/js/sales_invoice_doctype.js` (doctype_js).

- New Sales Invoice → `update_stock = 1` and `set_warehouse` prefilled from the user's default `Warehouse` `User Permission`.
- For users with the `Branch User` role **and none** of `Sales Manager`, `Sales Master Manager`, `Stock Manager`, `System Manager`, the `update_stock` field is marked `read_only` with a description `"Locked for Branch Users. Contact a Sales Manager to change."`.
- Credit Note handling stays — `is_return = 1` flips positive quantities to negative in `before_save`.

### 11.3 HR Defaults (`rmax_custom.hr_defaults`)

Runs in `after_migrate`. No-op if `hrms` app is absent.

| Artifact | Details |
|---------|---------|
| Employee Grades | `Sponsorship`, `Non-Sponsorship` (global) |
| Salary Components | `Basic`, `Housing Allowance`, `Transportation Allowance`, `Food Allowance`, `Other Allowance`, `GOSI Employee` (Deduction) |
| Salary Structure | `RMAX Sponsorship KSA - <CompanyAbbr>` per Company, Draft state. Earnings = `base × 0.60 / 0.25 / 0.10 / 0.05`. No default structure for Non-Sponsorship. |

Idempotent — existing rows are never touched again. Reset helper (admin only):
```
bench --site <site> execute rmax_custom.hr_defaults.reset_sponsorship_salary_structures --kwargs '{"force": 1}'
```
Refuses to delete submitted structures or those already assigned to an employee.

### 11.4 LCV Charge Template + Purchase Receipt Checklist

**DocTypes introduced** (module `Rmax Custom`):
- `LCV Charge Template` — top-level reusable list, unique by `template_name`, one default allowed at a time.
- `LCV Charge Template Item` (child) — fields: `charge_name`, `currency` (SAR/USD), `distribute_by` (CBM/Value), `default_amount`, `is_mandatory`.
- `Purchase Receipt LCV Checklist` (child on Purchase Receipt) — fields: `charge_name`, `expense_account`, `distribute_by`, `is_mandatory`, `done`, `lcv_reference`, `amount`.

**Shipped template** `Standard Import KSA` (is_default = 1) ships 11 rows with blank amounts:
Freight Sea/Air (USD, CBM), Duty (SAR, Value), DO Charges, Port Charges, Mawani, Fasah Appointment Fees, Custom Clearance Charges, Transportation to Warehouse, Doc Charges, Local Unloading Expense, Overtime (Kafeel) — all CBM SAR.

**Chart of Accounts setup** (`_ensure_accounts_per_company`)
- Group `Landed Cost Charges - <abbr>` under `Indirect Expenses` per root Company.
- 11 leaf Expense accounts, one per charge. `Freight Sea/Air` is booked in `account_currency = USD`.
- Child companies inherit via the ERPNext sync pattern.
- `_align_account_currency` re-stamps currency on an existing shipped account only when no `GL Entry` exists for it.

**Purchase Receipt custom fields** (all `allow_on_submit = 1`)
- `custom_lcv_template` (Link LCV Charge Template)
- `custom_lcv_status` (Select: Not Started / Pending / Partial / Complete; in list view + standard filter)
- `custom_lcv_checklist` (Table Purchase Receipt LCV Checklist)

**Server hooks**
| Hook | Purpose |
|------|---------|
| `Purchase Receipt.validate` → `purchase_receipt_validate` | Auto-populate checklist from the selected template when empty; recompute status |
| `Landed Cost Voucher.on_submit` → `landed_cost_voucher_on_submit` | Match LCV taxes against every linked PR's checklist by expense account, tick `done`, store `lcv_reference` + `amount`, refresh PR status |
| `Landed Cost Voucher.on_cancel` → `landed_cost_voucher_on_cancel` | Reverse only rows whose `lcv_reference` equals the cancelled LCV |

**Status rollup**
- 0 done → `Not Started`
- All done → `Complete`
- Mandatory all done with optional still pending → `Partial`
- Otherwise → `Pending`

**Whitelisted APIs**
- `rmax_custom.lcv_template.load_template_into_pr(purchase_receipt, template)`
- `rmax_custom.lcv_template.create_lcv_from_template(purchase_receipt)` — creates a Draft LCV containing only rows still pending; when every pending row is CBM, the LCV ships with `Distribute Manually + custom_distribute_by_cbm = 1` so the CBM override distributes automatically.

**Client (PR form)**
- Dashboard indicator coloured by status, showing `LCV <status> (done/total)`.
- `LCV Checklist > Load LCV Template` dialog.
- `LCV Checklist > Create LCV from Template` button (opens the created Draft LCV).

### 11.5 Permission Hygiene

- `setup.preserve_standard_docperms_on_touched_doctypes()` runs first in `after_migrate`, mirroring every standard DocPerm into Custom DocPerm on doctypes we extend. This avoids Frappe's "Custom DocPerm replaces standard" wipe and restores Accounts Manager / Sales User / Purchase User access on doctypes like Accounts Settings and Sales Invoice.
- Branch Configuration now force-upgrades any non-System user to `user_type = System User` before inserting `Has Role` so Branch/Stock/Stock Manager/Damage User roles actually stick.
- Stock User has been granted read access on `User Permission` and `Accounts Settings` via Custom DocPerm, matching what the Branch/Damage User roles already had.

### 11.6 LCV GL Distribution Patch

`rmax_custom.overrides.landed_cost_gl.apply_patch()` runs at import time (from `rmax_custom/__init__.py`) and replaces `erpnext.stock.doctype.purchase_receipt.purchase_receipt.get_item_account_wise_additional_cost`. The patched version uses `custom_cbm` as the distribution basis whenever an LCV has `distribute_charges_based_on = "Distribute Manually"` **and** `custom_distribute_by_cbm = 1`. Without the patch, multiple tax rows under Manual mode produced duplicate Cr entries and a GL imbalance equal to the extra tax rows' amounts.

### 11.7 Deployment Map

| Site | Server | Server ID |
|------|--------|-----------|
| rmax_dev2 | RMAX (5.189.131.148) | `41ef79dc-a2fd-418a-bd88-b5f5173aeaf7` |
| rmax-uat2.enfonoerp.com | AQRAR (185.193.19.184) | `3beb2d91-86d1-4d2d-ba0b-30955992455c` |

Always deploy to both. UAT `bench migrate` is currently blocked by missing ERPNext patch `v11_1.rename_depends_on_lwp`; use `bench execute rmax_custom.setup.after_migrate` for non-schema changes and `bench execute frappe.reload_doc` + `frappe.custom.doctype.custom_field.custom_field.create_custom_fields` for new DocTypes / Custom Fields.
