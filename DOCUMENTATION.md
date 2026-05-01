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
12. [Inter-Branch Receivables & Payables](#12-inter-branch-receivables--payables-phase-1--15--2)
13. [BNPL — Tabby / Tamara Surcharge Uplift](#13-bnpl--tabby--tamara-surcharge-uplift)
14. [Inter-Company Delivery Note → Consolidated Sales Invoice](#14-inter-company-delivery-note--consolidated-sales-invoice)

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
| `branch` | Link → Branch | The branch this config belongs to |
| `user` | Table → Branch Configuration User | Users assigned to this branch |
| `warehouse` | Table → Branch Configuration Warehouse | Warehouses for this branch |
| `cost_center` | Table → Branch Configuration Cost Center | Cost centers for this branch |

**Behavior:**
- On save, automatically creates `User Permission` records for each user, granting access to the branch, its warehouses, and cost centers.
- On user removal, automatically deletes the corresponding `User Permission` records.
- Permissions are set with `apply_to_all_doctypes = 1`.

**Child Tables:**
- **Branch Configuration User** — fields: `user` (Link → User)
- **Branch Configuration Warehouse** — fields: `warehouse` (Link → Warehouse)
- **Branch Configuration Cost Center** — fields: `cost_center` (Link → Cost Center)

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

### 2.3 Stock Transfer

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
| `rmax_custom.api.sales_invoice_payment.get_payment_modes_with_account` | Whitelisted | Returns enabled Mode of Payment names that have a default account for the company. Optionally filters by a provided list (from POS Profile). |
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

# Document events
doc_events = {
    "Sales Invoice": {
        "on_submit": "rmax_custom.inter_company.sales_invoice_on_submit",
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
| `Sales Invoice Item-total_vat_linewise` | Per-line VAT total |
| `Quotation-custom_payment_mode` | Payment mode on quotation |
| `Quotation Item-total_vat_linewise` | Per-line VAT total |
| `Landed Cost Voucher-custom_distribute_by_cbm` | CBM distribution toggle |
| `Landed Cost Item-custom_cbm` | CBM value per item |
| `Customer-custom_vat_registration_number` | Saudi VAT number |

### Property Setters Exported

Material Request fields simplified for transfer workflow. Customer type extended with "Branch". Landed Cost Item qty column shown.

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

---

## 12. Inter-Branch Receivables & Payables (Phase 1 + 1.5 + 2)

Single-company multi-branch GL. Implementation in `rmax_custom/inter_branch.py`.

**Status:** deployed on `feature/inter-branch-rp-phase1` to `rmax_dev2` only. Not yet on `main`. Not on UAT.

**Plan:** [docs/superpowers/plans/2026-04-28-inter-branch-rp-foundation.md](docs/superpowers/plans/2026-04-28-inter-branch-rp-foundation.md)
**User guide:** [docs/user-guides/inter-branch-receivables-payables.md](docs/user-guides/inter-branch-receivables-payables.md)

### 12.1 Custom Fields

| DocType | Field | Type | Purpose |
|---------|-------|------|---------|
| Journal Entry Account | `custom_auto_inserted` | Check | Flag for auto-injected legs (read-only) |
| Journal Entry Account | `custom_source_doctype` | Link → DocType | Source traceability (child) |
| Journal Entry Account | `custom_source_docname` | Dynamic Link | Source doc name (child) |
| Journal Entry | `custom_source_doctype` | Link → DocType | Header mirror; powers Connections sidebar finder |
| Journal Entry | `custom_source_docname` | Dynamic Link | Header mirror; finder lookup field for `non_standard_fieldnames` |
| Company | `custom_inter_branch_cut_over_date` | Date | Activation gate; entries before this date are not auto-injected |
| Company | `custom_inter_branch_bridge_branch` | Link → Branch | Implicit counterparty for 3+ branch JEs (Phase 1.5) |

### 12.2 Chart of Accounts (auto-managed)

For every root Company (`parent_company` IS NULL/empty):
- `Inter-Branch Receivable - <abbr>` — Group, root_type=Asset, parent=Current Assets
- `Inter-Branch Payable - <abbr>` — Group, root_type=Liability, parent=Current Liabilities

Lazy leaves on demand: `Due from <Branch> - <abbr>` (Asset) and `Due to <Branch> - <abbr>` (Liability), created the first time a JE references the counterparty. ERPNext auto-syncs to child companies when the root creates the parent group.

`Branch.after_insert` hook (`on_branch_insert`) creates leaves both directions for every existing Branch when a new Branch is inserted.

### 12.3 Auto-Injector (`auto_inject_inter_branch_legs`)

Hook: `Journal Entry.validate` (chained AFTER `bnpl_clearing_guard.warn_bnpl_clearing_overdraw`).

Computes per-branch (debit − credit) imbalance.
- 0 or 1 branch → no-op.
- 2 branches → infer counterparty from imbalance signs; inject 2 legs.
- 3+ branches → require `Company.custom_inter_branch_bridge_branch`; bridge must appear in JE; pair every non-bridge against bridge (2 × (N−1) injected legs).

Idempotent: strips existing auto-injected rows before recomputing.
Final guard: re-checks per-branch balance after injection; throws if any branch still off.

Skip conditions: doctype mismatch, `flags.skip_inter_branch_injection`, no company, JE dated before Company cut-over.

### 12.4 Stock Movement Integration

Two paths produce identical accounting:

**Path A — Stock Transfer wrapper (existing custom workflow)**
- `Stock Transfer.on_submit` calls `create_companion_inter_branch_je_for_stock_transfer(self)` after creating the Stock Entry
- Sets `flags.from_stock_transfer = True` on the SE so Path B short-circuits
- Companion JE source = `Stock Transfer / ST-XXXX`

**Path B — Direct Stock Entry (Material Transfer)**
- `Stock Entry.on_submit` → `on_stock_entry_submit`
- Resolves source/target warehouse → branch via `resolve_warehouse_branch()` (Branch Configuration → Warehouse mapping)
- Same-branch pair (e.g. WH-HO-1 ↔ WH-HO-2 both under HO) → no companion JE; standard SE GL is sufficient
- Cross-branch single-pair → re-tags SE GL Entries per leg via `_retag_se_gl_entries`, then creates companion JE
- Multi-pair (different src/tgt across rows) → logs hint to Error Log and skips
- `Stock Entry.on_cancel` → `on_stock_entry_cancel` cancels JEs sourced from this SE

Skip conditions on Path B: `flags.from_stock_transfer`, purpose ≠ `Material Transfer`, no company, idempotent JE-already-exists check.

### 12.5 Reconciliation Report

Path: `rmax_custom/rmax_custom/report/inter_branch_reconciliation/`
- Frappe Script Report. Matrix: rows = from_branch, cols = to_branch.
- Health check: every pair (A→B + B→A) must net to zero. Non-zero pairs flag missing counterparty tags, unbalanced manual JEs, or timing differences.
- Roles: Accounts Manager / Accounts User / Auditor / System Manager.
- Debug helper: `rmax_custom.inter_branch.print_reconciliation(company, from_date, to_date)` — whitelisted, prints to stdout via `bench execute`.

### 12.6 Hooks Registered

```python
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
    "validate":  "rmax_custom.inter_branch.auto_set_branch_from_warehouse",
    "on_submit": "rmax_custom.inter_branch.on_stock_entry_submit",
    "on_cancel": "rmax_custom.inter_branch.on_stock_entry_cancel",
},
"Stock Reconciliation": {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
"Purchase Receipt":     {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
"Delivery Note":        {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
"Purchase Invoice":     {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
"Sales Invoice":        {"validate": "rmax_custom.inter_branch.auto_set_branch_from_warehouse"},
```

```python
override_doctype_dashboards = {
    "Material Request": "rmax_custom.api.dashboard_overrides.material_request_dashboard",
    "Stock Transfer":   "rmax_custom.api.dashboard_overrides.stock_transfer_dashboard",
    "Stock Entry":      "rmax_custom.api.dashboard_overrides.stock_entry_dashboard",
}

doctype_js = {
    # ...,
    "Stock Entry": "public/js/stock_entry_inter_branch.js",
}
```

### 12.6a Branch Auto-Fill (`auto_set_branch_from_warehouse`)

Hook target: stock-side doctypes whose item rows carry a warehouse field (or `s_warehouse` / `t_warehouse` for Stock Entry).

Behaviour:
- Iterates `doc.items`. For each row with empty `branch`, looks up via `resolve_warehouse_branch(warehouse | s_warehouse | t_warehouse)` and writes the result to `item.branch`.
- Header `branch` is set to the first row that resolves successfully (operator override is preserved).
- A row whose warehouse has no Branch Configuration mapping is left untouched — ERPNext will throw the standard *"Accounting Dimension Branch is required for 'Balance Sheet' account..."* on submit. Map the warehouse to fix.

This avoids the per-Company `mandatory_for_bs` rejection on Stock Reconciliation, opening stock, and routine Purchase Receipt / Delivery Note / Invoice flows.

### 12.6b UI Surfacing — Companion JE on Stock Entry / Stock Transfer

Two paths surface the linked JE (both backed by the JE header `custom_source_doctype` + `custom_source_docname` denormalisation):

**Server-side dashboard (Connections sidebar)** — `rmax_custom/api/dashboard_overrides.py`:
- `stock_transfer_dashboard(data)` and `stock_entry_dashboard(data)` add a `Journal Entry` connection card under an "Inter-Branch" section.
- Both set `non_standard_fieldnames["Journal Entry"] = "custom_source_docname"` so Frappe's connection finder filters JEs by `custom_source_docname = <SE/ST.name>`.

**Client-side button + sidebar** — `rmax_custom/public/js/stock_entry_inter_branch.js`:
- Triggers on submitted `Stock Entry` with `purpose = Material Transfer`.
- Queries `Journal Entry Account` rows with `custom_source_doctype = "Stock Entry"` AND `custom_source_docname = SE.name` AND `docstatus = 1`.
- For each parent JE found: adds a custom button labelled `Inter-Branch JE → ACC-JV-...` and a sidebar badge that navigates to the JE on click.

The JS path uses the JE Account child rows (not header) so it works against pre-Phase-2 JEs that haven't been backfilled yet.

### 12.6c Backfill Helper

`rmax_custom.inter_branch.backfill_je_header_source()` — whitelisted.

Populates the new `custom_source_doctype` + `custom_source_docname` fields on JE header for already-submitted companion JEs created before the dashboard work landed.
- Idempotent. Only updates JEs whose header is empty AND whose child auto-injected rows agree on a single source.
- Run: `bench --site rmax_dev2 execute rmax_custom.inter_branch.backfill_je_header_source`
- Returns the number of JEs updated.

### 12.7 Activation Per Company

1. Set `Inter-Branch Cut-Over Date` on the Company (auto-injector OFF until set).
2. Set `Inter-Branch Bridge Branch` on the Company if multi-branch (3+) JEs are needed.
3. Foundation runs from `setup.after_migrate` (`setup_inter_branch_foundation`) — idempotent, tolerant.

### 12.8 Out of Scope (Deferred)

- Settlement / Clearing
- Salary / Expense Claim / Vendor-on-behalf
- Branch-wise TB/P&L/BS reports beyond reconciliation
- HO overhead allocation
- Historical restate

### 12.9 Deployed Bug History

1. `setup_inter_branch_foundation` originally iterated all companies including ERPNext children → `validate_root_company_and_sync_account_to_children` rejected. Fix: filter to `parent_company in ("", None)`.
2. Auto-injected JE Account rows had only `*_in_account_currency` fields — ERPNext's `make_gl_entries` skipped them because company-currency `debit/credit` were 0. Fix: also set `account_currency`, `exchange_rate=1`, and company-currency `debit/credit`.
3. Direct Stock Entry between mapped + unmapped warehouse pair (e.g. Malaz → Damage Riyadh) silently skipped companion JE creation — `_stock_entry_branch_pair` returned `(None, None, 0.0)` because the unmapped target had no branch. By design, but operationally surprising. Fix is policy-side: map all stock-bearing warehouses (including Damage WHs) in Branch Configuration.
4. Stock Reconciliation / opening stock submission rejected with *"Accounting Dimension Branch is required for 'Balance Sheet' account Stock In Hand - CNC"* because the user did not pick Branch on item rows. Fix: `auto_set_branch_from_warehouse` validate hook on Stock Reconciliation / Purchase Receipt / Delivery Note / Purchase Invoice / Sales Invoice / Stock Entry — auto-fills `branch` from each item's warehouse mapping.
5. Companion JE not visible from the source Stock Entry / Stock Transfer form — Frappe's standard dashboard cannot follow via-child-table dynamic-link references. Fix: denormalise `custom_source_doctype` + `custom_source_docname` to JE header (new Custom Fields), register dashboard overrides for SE + ST, add `stock_entry_inter_branch.js` for top-bar button + sidebar badges. Backfill helper updates pre-existing companion JE headers.

### 12.10 Operational Notes

**Warehouse mapping requirement.** Every leaf warehouse on a Company that posts to GL must appear in at least one `Branch Configuration → Warehouses` child table row. Without the mapping:
- Stock-side documents fail with the dimension error (auto-fill cannot resolve)
- Direct Stock Entry inter-branch hook silently skips companion JE creation
- Reconciliation report under-counts the unmapped warehouse's GL on the from-branch row

**Damage warehouses (RMAX policy decision).** Damage warehouses (`Damage Jeddah - CNC`, `Damage Riyadh - CNC`) need branch assignment. Three policy options, one must be picked before damage transfers post correctly:
- Per-city: `Damage Jeddah → Jeddah branch`, `Damage Riyadh → Riyadh branch`. Damage write-off stays branch-local; cross-branch damage transfer becomes inter-branch obligation.
- Centralized: all damage WHs → HO. Any branch → its city's Damage WH = inter-branch obligation to HO.
- Dedicated: all damage WHs → a `Damage` branch. Cleanest separation if damage P&L is its own center.

**Valuation passthrough.** The companion JE inherits the source SE's valuation (`item.basic_amount` or `qty * basic_rate`) which comes from ERPNext's Bin valuation. Inter-branch is NOT the source of truth for valuation. If a JE looks "wildly wrong", trace via `Stock Ledger Entry` filtered by item + warehouse → identify the offending Purchase Receipt / Stock Reconciliation / LCV → cancel + re-post → cancel + re-create the SE/ST.

**Cancel reversal.** Cancelling Stock Entry or Stock Transfer auto-cancels the linked companion JE through the `on_cancel` hook. Reversal posts cancelling GL Entries.

**Multi-pair Stock Entry.** Phase 1 supports single-pair only. SEs with rows moving across multiple branch pairs are logged to Error Log as *"Inter-Branch SE skipped (multi-pair)"* and the companion JE is not created. Operations splits multi-pair SEs into one Material Transfer per pair.

---

## 13. BNPL — Tabby / Tamara Surcharge Uplift

Three-part feature for BNPL ("Buy Now Pay Later") payment providers. Implementation across `rmax_custom/bnpl_uplift.py`, `bnpl_settlement_setup.py`, `bnpl_clearing_guard.py`.

### 13.1 Concept

BNPL providers absorb a fee (~8.6957%). To preserve margin, the customer pays an uplifted price computed from:

```
new_rate = original_rate * (1 + bnpl_portion_ratio * surcharge_pct / 100)
```

The uplift modifies the selling-side rate ONLY. COGS, Stock Ledger, and item valuation are not touched — margin is preserved by passing the surcharge through to the customer.

After settlement, BNPL deposits the gross-of-fee amount minus their commission to the Bank. The Clearing account holds the receivable until then; reconciliation against Bank statement uses standard ERPNext Bank Reconciliation.

### 13.2 Provisioning (`bnpl_settlement_setup.setup_bnpl_accounts`)

Idempotent. Called from `setup.after_migrate`. Per root Company creates:

| Account | Type | Parent |
|---|---|---|
| `Tabby Clearing - <abbr>` | Bank | Bank Accounts |
| `Tamara Clearing - <abbr>` | Bank | Bank Accounts |
| `BNPL Fee Expense - <abbr>` | Expense | Indirect Expenses |

Sets `Company.custom_bnpl_fee_account` to the per-Company fee account.

Mode of Payment records (`Tabby`, `Tamara`) are NOT auto-created or mutated — operator wires `custom_surcharge_percentage` + clearing account on the Mode of Payment form.

### 13.3 Custom Fields

| DocType | Field | Type | Purpose |
|---|---|---|---|
| Mode of Payment | `custom_surcharge_percentage` | Float | Non-zero flags MoP as BNPL |
| Mode of Payment | `custom_bnpl_clearing_account` | Link → Account | BNPL receivable account |
| Sales Invoice | `custom_bnpl_portion_ratio` | Float | Portion of total paid via BNPL (0..1) |
| Sales Invoice | `custom_bnpl_total_uplift` | Currency | Sum of per-item uplifts |
| Sales Invoice | `custom_payment_mode` | Link → Mode of Payment | Quick-pick payment mode (POS) |
| Sales Invoice | `custom_pos_payments_json` | Long Text | POS payment breakdown (used when Payments table is empty) |
| Sales Invoice Item | `custom_original_rate` | Currency | Pre-uplift selling rate |
| Sales Invoice Item | `custom_bnpl_uplift_amount` | Currency | This row's uplift in SAR |
| Quotation | `custom_payment_mode` | Link → Mode of Payment | Same uplift logic at quotation time |
| Quotation Item | `custom_bnpl_uplift_amount` | Currency | Per-line uplift |
| Company | `custom_bnpl_fee_account` | Link → Account | Per-Company BNPL fee expense |

### 13.4 Server-Side Hooks

**`Sales Invoice.before_validate` → `bnpl_uplift.apply_uplift`**
- Reads payment breakdown from one of (priority order): Payments child table, `custom_pos_payments_json`, `custom_payment_mode`.
- For each row whose Mode of Payment has non-zero `custom_surcharge_percentage`, computes per-item uplift and stamps `custom_original_rate` + new `rate`.

**`Sales Invoice.validate` → `bnpl_uplift.verify_uplift_invariants`**
- Re-checks `new_rate ≈ original_rate * (1 + ratio * pct / 100)` after ERPNext's own calculations.
- Tolerance: 0.01 SAR per row.
- Throws on drift to block submit.

**`Journal Entry.validate` → `bnpl_clearing_guard.warn_bnpl_clearing_overdraw`**
- Chained BEFORE the inter-branch auto-injector.
- Soft warning (`msgprint`, no throw) when a JE credits more than the live GL balance of a BNPL clearing account.
- Submission allowed — finance reviews the message and proceeds.
- The set of "BNPL clearing accounts" = union of `default_account` values from `Mode of Payment Account` rows whose parent MoP has positive `custom_surcharge_percentage` (scoped per Company).

### 13.5 Client-Side

- `sales_invoice_doctype.js` mirrors the uplift formula for live recalculation in the form (POS + standard).
- `sales_invoice_pos_total_popup.v2.js` handles POS payment popup. Respects branch MoP allowlist via `branch_defaults.override_payment_accounts_from_branch` (server-side hook strips/migrates MoPs not in the branch's allowed list).

### 13.6 Cancellation

Cancelling a BNPL Sales Invoice reverses the uplift through ERPNext's standard SI cancel flow. The clearing-account credit reverses with it.

### 13.7 One-Time Migrations Already Shipped

Removed Settlement-related DocTypes + reports (commits `02a9cf5`, `a007d74`, `628ef99`). The Settlement layer is no longer part of RMAX — settlement reconciliation happens via standard Bank Reconciliation against Tabby/Tamara clearing accounts.

---

## 14. Inter-Company Delivery Note → Consolidated Sales Invoice

Implementation: `rmax_custom/inter_company_dn.py`.

> **Naming caution.** This is for ERPNext **multi-COMPANY** flows (separate companies, distinct ledgers). Distinct from the Phase 1 **Inter-BRANCH** R/P module (`inter_branch.py`) which handles single-company multi-branch GL.

### 14.1 Trigger

List action on Delivery Note: select 2+ submitted inter-company DNs → "Create Inter-Company SI" → calls whitelisted `inter_company_dn.create_si_from_multiple_dns(delivery_note_names)`.

No auto-creation on individual DN submit — consolidation is always explicit per client requirement.

### 14.2 Validation Per Batch

Every selected DN must satisfy:
- `docstatus = 1` (submitted)
- `custom_is_inter_company = 1`
- Share `customer`
- Share `represents_company`
- Share `currency`
- Share `custom_inter_company_branch`
- Not already linked to a non-cancelled SI via `custom_inter_company_si`

The Inter Company Branch master must exist and define the source warehouse + cost center for the buying side's PI auto-creation.

### 14.3 Output SI

- Issued by the SELLING company (typically Head Office).
- Inherits taxes from the FIRST selected DN.
- `cost_center` and `set_warehouse` come from the matching `Inter Company Branch` row for the selling Company.
- `update_stock = 0` (DNs already moved stock; SI is purely the inter-company invoice).
- Each row mirrors the underlying DN line at the inter-company price (uses the `Inter Company Price` Price List, auto-created by `setup_inter_company_price_list` from `after_migrate`).

### 14.4 DN Stamping

After SI insertion, each source DN is stamped:
- `custom_inter_company_si = <SI.name>` (Link to the consolidated SI)
- `custom_inter_company_status = "Consolidated"` (Select)

Cancelling the SI (`sales_invoice_on_cancel` hook) clears those stamps so the DNs become eligible for a different SI batch.

### 14.5 Custom Fields on Delivery Note

| Field | Type | Purpose |
|---|---|---|
| `custom_is_inter_company` | Check | Flags the DN as inter-company; restricts customer dropdown to inter-company entities |
| `custom_inter_company_branch` | Link → Inter Company Branch | Branch master row used for default warehouse + cost center |
| `custom_inter_company_si` | Link → Sales Invoice | Backlink to the consolidated SI |
| `custom_inter_company_status` | Select | Not Consolidated / Consolidated |

### 14.6 Inter Company Branch DocType (RMAX Custom)

- Maps the relationship: which (Selling Company, Buying Company) pair → which Cost Center + Warehouse for auto-created PIs.
- Child table: `Inter Company Branch Cost Center` for per-buying-company cost center mapping.
- Used by `inter_company.sales_invoice_on_submit` to auto-create the buying-side PI from a submitted inter-company SI.

### 14.7 Hooks Registered

```python
"Sales Invoice": {
    "on_submit": "rmax_custom.inter_company.sales_invoice_on_submit",
    "on_cancel": "rmax_custom.inter_company_dn.sales_invoice_on_cancel",
}
```

### 14.8 Client-Side

`delivery_note_doctype.js` exposes the "Create Inter-Company SI" list action via `frappe.listview_settings`. Validates selection count + submission status before calling the whitelisted endpoint.
