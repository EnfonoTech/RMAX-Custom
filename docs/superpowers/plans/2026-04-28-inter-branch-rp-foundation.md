# Inter-Branch Receivables & Payables — Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture inter-branch receivables and payables within a single legal entity (one Company, multiple branches) so each branch's books balance independently while consolidated Trial Balance remains naturally balanced. Phase 1 covers Cash, Stock, and Rent scenarios only.

**Architecture:** Branch becomes a mandatory accounting dimension on every GL-posting DocType. Two parent account groups (`Inter-Branch Receivable`, `Inter-Branch Payable`) hold lazily-created leaves per counterparty branch. A `Journal Entry.validate` hook auto-injects balancing inter-branch legs whenever per-branch debits ≠ credits. Cross-branch Stock Entries get a companion Journal Entry generated on Stock Transfer approval. Every auto-injected leg is flagged and links back to its source document for full traceability. A reconciliation matrix report verifies diagonal pairs net to zero.

**Tech Stack:** Frappe Framework v15, ERPNext v15, Python 3.11, Frappe Accounting Dimensions, Custom Fields, Custom DocPerms, Frappe Script Reports.

**Deploy target:** `rmax_dev2` site only for Phase 1. UAT deployment deferred until soak passes on dev.

---

## Critical Constraints (read before starting)

1. **Permission preservation** (CLAUDE.md gotcha #10): Custom DocPerm replaces standard. `setup.preserve_standard_docperms_on_touched_doctypes()` must run before any DocPerm change. We are NOT touching DocPerms in this plan, but new Custom Fields on Journal Entry must not break Accounts Manager / Accounts User access.
2. **UAT migrate is blocked** (gotcha #11). All schema changes must be safely re-runnable via `bench execute frappe.reload_doc` + `bench execute frappe.custom.doctype.custom_field.custom_field.create_custom_fields` workaround when we eventually deploy to UAT.
3. **Account currency freeze** (gotcha #12): newly created Inter-Branch leaf accounts must be created in the parent Company's default currency from the start. Once any GL Entry posts, currency cannot change.
4. **Idempotent `after_migrate`**: every account / dimension / leaf creation must be safe to re-run.
5. **Naming collision**: existing `Inter Company Branch` DocType is for ERPNext multi-company auto-PI. Do NOT confuse with this work. New code lives in `inter_branch.py` (singular, no underscore "company").
6. **Cut-over date**: Phase 1 is prospective only. No restate of historical entries. The auto-injector skips JEs with `posting_date` before the cut-over date stored on Company.
7. **Don't break existing branch-aware overrides**: `branch_defaults.override_cost_center_from_branch` already mutates JE/SI/PI/PE before validate. Our new `Journal Entry.validate` hook must run AFTER `before_validate` is done (Frappe ordering: `before_validate` → `validate`).

---

## File Structure

### Files to create

| Path | Responsibility |
|------|----------------|
| `rmax_custom/inter_branch.py` | Core module: dimension setup, COA group setup, lazy leaf creation, Branch.after_insert handler, JE auto-injector, branch resolver helpers |
| `rmax_custom/test_inter_branch.py` | Unit tests using `FrappeTestCase` |
| `rmax_custom/rmax_custom/report/inter_branch_reconciliation/__init__.py` | Empty module init |
| `rmax_custom/rmax_custom/report/inter_branch_reconciliation/inter_branch_reconciliation.json` | Frappe Script Report metadata |
| `rmax_custom/rmax_custom/report/inter_branch_reconciliation/inter_branch_reconciliation.py` | Report data builder |
| `rmax_custom/rmax_custom/report/inter_branch_reconciliation/inter_branch_reconciliation.js` | Report client filters |

### Files to modify

| Path | Change |
|------|--------|
| `rmax_custom/hooks.py` | Add `doc_events`: `Journal Entry.validate`, `Branch.after_insert`. Extend Custom Field fixture filter list. |
| `rmax_custom/setup.py` | Call `inter_branch.setup_inter_branch_foundation()` from `after_migrate`. |
| `rmax_custom/rmax_custom/doctype/stock_transfer/stock_transfer.py` | After `create_stock_entry()`, call `inter_branch.create_companion_inter_branch_je_for_stock_transfer(self)` when source/target branches differ. |
| `rmax_custom/fixtures/custom_field.json` | Append 3 new Custom Field rows on `Journal Entry Account`: `custom_auto_inserted`, `custom_source_doctype`, `custom_source_docname`. Append `Company-custom_inter_branch_cut_over_date`. |

---

## Module Skeleton — `rmax_custom/inter_branch.py`

The module exposes these public callables (defined across the tasks below):

- `setup_inter_branch_foundation()` — idempotent post-migrate entrypoint
- `_ensure_branch_accounting_dimension()` — enables Branch as Accounting Dimension and marks mandatory on JE/SE/PE
- `_ensure_inter_branch_groups(company)` — creates `Inter-Branch Receivable` (Asset) and `Inter-Branch Payable` (Liability) groups
- `get_or_create_inter_branch_account(company, counterparty_branch, side)` — `side` ∈ `{"receivable", "payable"}`; lazy leaf
- `resolve_warehouse_branch(warehouse)` — looks up the Branch linked to a warehouse via `Branch Configuration Warehouse` reverse map
- `on_branch_insert(doc, method=None)` — Branch.after_insert hook; creates leaves for the new branch and emits a `frappe.msgprint` warning
- `auto_inject_inter_branch_legs(doc, method=None)` — Journal Entry.validate hook
- `create_companion_inter_branch_je_for_stock_transfer(stock_transfer_doc)` — invoked from Stock Transfer.on_submit after Stock Entry is created

---

## Tasks

### Task 1: Add custom fields on Journal Entry Account + Company cut-over date

**Files:**
- Modify: `rmax_custom/fixtures/custom_field.json` (append 4 rows)
- Modify: `rmax_custom/hooks.py:332-` (extend Custom Field fixture filter list)

- [ ] **Step 1: Append 4 rows to `rmax_custom/fixtures/custom_field.json`**

Append before the closing `]`. Use existing rows in the file as a template for the schema (preserve every field key, defaults, etc.).

```json
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "default": "0",
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Journal Entry Account",
 "fieldname": "custom_auto_inserted",
 "fieldtype": "Check",
 "hidden": 0,
 "in_list_view": 0,
 "in_standard_filter": 0,
 "insert_after": "credit",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Auto-Inserted (Inter-Branch)",
 "modified": "2026-04-28 00:00:00.000000",
 "name": "Journal Entry Account-custom_auto_inserted",
 "no_copy": 1,
 "non_negative": 0,
 "permlevel": 0,
 "print_hide": 1,
 "read_only": 1,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "translatable": 0,
 "unique": 0
},
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Journal Entry Account",
 "fieldname": "custom_source_doctype",
 "fieldtype": "Link",
 "options": "DocType",
 "hidden": 0,
 "in_list_view": 0,
 "in_standard_filter": 0,
 "insert_after": "custom_auto_inserted",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Source DocType",
 "modified": "2026-04-28 00:00:00.000000",
 "name": "Journal Entry Account-custom_source_doctype",
 "no_copy": 1,
 "non_negative": 0,
 "permlevel": 0,
 "print_hide": 1,
 "read_only": 1,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 1,
 "translatable": 0,
 "unique": 0
},
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Journal Entry Account",
 "fieldname": "custom_source_docname",
 "fieldtype": "Dynamic Link",
 "options": "custom_source_doctype",
 "hidden": 0,
 "in_list_view": 0,
 "in_standard_filter": 0,
 "insert_after": "custom_source_doctype",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Source Document",
 "modified": "2026-04-28 00:00:00.000000",
 "name": "Journal Entry Account-custom_source_docname",
 "no_copy": 1,
 "non_negative": 0,
 "permlevel": 0,
 "print_hide": 1,
 "read_only": 1,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 1,
 "translatable": 0,
 "unique": 0
},
{
 "allow_in_quick_entry": 0,
 "allow_on_submit": 0,
 "bold": 0,
 "collapsible": 0,
 "columns": 0,
 "docstatus": 0,
 "doctype": "Custom Field",
 "dt": "Company",
 "fieldname": "custom_inter_branch_cut_over_date",
 "fieldtype": "Date",
 "hidden": 0,
 "in_list_view": 0,
 "in_standard_filter": 0,
 "insert_after": "default_finance_book",
 "is_system_generated": 0,
 "is_virtual": 0,
 "label": "Inter-Branch Cut-Over Date",
 "description": "Inter-branch auto-injection only applies to Journal Entries dated on or after this date.",
 "modified": "2026-04-28 00:00:00.000000",
 "name": "Company-custom_inter_branch_cut_over_date",
 "no_copy": 0,
 "non_negative": 0,
 "permlevel": 0,
 "print_hide": 1,
 "read_only": 0,
 "report_hide": 0,
 "reqd": 0,
 "search_index": 0,
 "translatable": 0,
 "unique": 0
}
```

- [ ] **Step 2: Extend the Custom Field fixture filter in `rmax_custom/hooks.py`**

In the `fixtures` block, find the `"Custom Field"` filter list and append these 4 names to the existing `["name", "in", [...]]` list:

```
"Journal Entry Account-custom_auto_inserted",
"Journal Entry Account-custom_source_doctype",
"Journal Entry Account-custom_source_docname",
"Company-custom_inter_branch_cut_over_date",
```

- [ ] **Step 3: Apply custom fields locally**

Run on dev server (after pushing this change):
```
sudo -u v15 bench --site rmax_dev2 migrate
```
Expected: migrate completes without errors. Verify with:
```
sudo -u v15 bench --site rmax_dev2 execute 'frappe.db.exists' --kwargs '{"dt": "Custom Field", "dn": "Journal Entry Account-custom_auto_inserted"}'
```
Expected: returns the docname (truthy).

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/fixtures/custom_field.json rmax_custom/hooks.py
git commit -m "feat(inter-branch): add custom fields for auto-injected JE legs and Company cut-over date"
```

---

### Task 2: Foundation module skeleton + branch accounting dimension

**Files:**
- Create: `rmax_custom/inter_branch.py`
- Create: `rmax_custom/test_inter_branch.py`

- [ ] **Step 1: Write the failing test for `_ensure_branch_accounting_dimension`**

Create `rmax_custom/test_inter_branch.py`:

```python
"""Tests for inter-branch foundation module."""
from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from rmax_custom import inter_branch


class TestBranchAccountingDimension(FrappeTestCase):
    def test_creates_branch_accounting_dimension_idempotent(self):
        inter_branch._ensure_branch_accounting_dimension()
        first = frappe.db.exists("Accounting Dimension", {"document_type": "Branch"})
        self.assertIsNotNone(first)

        # Re-running must not raise or duplicate
        inter_branch._ensure_branch_accounting_dimension()
        second = frappe.db.exists("Accounting Dimension", {"document_type": "Branch"})
        self.assertEqual(first, second)

    def test_branch_dimension_mandatory_on_journal_entry(self):
        inter_branch._ensure_branch_accounting_dimension()
        detail = frappe.db.get_value(
            "Accounting Dimension Detail",
            {"parent": frappe.db.get_value("Accounting Dimension", {"document_type": "Branch"}),
             "document_type": "Journal Entry"},
            ["mandatory_for_bs", "mandatory_for_pl"],
            as_dict=True,
        )
        self.assertTrue(detail)
        self.assertEqual(detail.mandatory_for_bs, 1)
        self.assertEqual(detail.mandatory_for_pl, 1)
```

- [ ] **Step 2: Run test to verify it fails**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch
```
Expected: ImportError or AttributeError because `inter_branch._ensure_branch_accounting_dimension` does not exist yet.

- [ ] **Step 3: Create `rmax_custom/inter_branch.py` with the dimension function**

```python
"""Inter-Branch Receivables & Payables — Phase 1 Foundation.

Single-company multi-branch GL: enables branch as a mandatory accounting
dimension, manages the Inter-Branch chart-of-accounts groups + lazy leaves,
auto-injects balancing inter-branch legs into Journal Entries, and generates
a companion inter-branch JE for cross-branch Stock Transfers.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

# DocTypes that must carry a non-null Branch on every GL-posting line.
MANDATORY_BRANCH_DOCTYPES = (
    "Journal Entry",
    "Stock Entry",
    "Payment Entry",
)


def _ensure_branch_accounting_dimension() -> None:
    """Enable Branch as an Accounting Dimension and mark mandatory.

    Idempotent: safe to re-run from after_migrate.
    """
    dim_name = frappe.db.get_value("Accounting Dimension", {"document_type": "Branch"})
    if not dim_name:
        dim = frappe.new_doc("Accounting Dimension")
        dim.document_type = "Branch"
        dim.disabled = 0
        dim.insert(ignore_permissions=True)
        dim_name = dim.name

    dim = frappe.get_doc("Accounting Dimension", dim_name)

    existing_targets = {row.document_type for row in dim.dimension_defaults or []}
    for dt in MANDATORY_BRANCH_DOCTYPES:
        if dt in existing_targets:
            for row in dim.dimension_defaults:
                if row.document_type == dt:
                    row.mandatory_for_bs = 1
                    row.mandatory_for_pl = 1
        else:
            dim.append(
                "dimension_defaults",
                {
                    "document_type": dt,
                    "mandatory_for_bs": 1,
                    "mandatory_for_pl": 1,
                    "reference_document": "Branch",
                },
            )

    dim.save(ignore_permissions=True)
    frappe.db.commit()


def setup_inter_branch_foundation() -> None:
    """Idempotent entrypoint called from setup.after_migrate."""
    _ensure_branch_accounting_dimension()
```

- [ ] **Step 4: Run test to verify it passes**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/inter_branch.py rmax_custom/test_inter_branch.py
git commit -m "feat(inter-branch): add branch accounting dimension setup"
```

---

### Task 3: Inter-Branch chart-of-accounts groups (per Company)

**Files:**
- Modify: `rmax_custom/inter_branch.py`
- Modify: `rmax_custom/test_inter_branch.py`

- [ ] **Step 1: Write the failing test for `_ensure_inter_branch_groups`**

Append to `rmax_custom/test_inter_branch.py`:

```python
class TestInterBranchGroups(FrappeTestCase):
    def setUp(self):
        self.company = frappe.db.get_value("Company", {}, "name")
        self.assertIsNotNone(self.company, "Test environment requires at least one Company")

    def test_creates_receivable_and_payable_group_accounts(self):
        inter_branch._ensure_inter_branch_groups(self.company)

        abbr = frappe.db.get_value("Company", self.company, "abbr")
        receivable = f"Inter-Branch Receivable - {abbr}"
        payable = f"Inter-Branch Payable - {abbr}"

        self.assertTrue(frappe.db.exists("Account", receivable))
        self.assertTrue(frappe.db.exists("Account", payable))

        rec_root = frappe.db.get_value("Account", receivable, "root_type")
        pay_root = frappe.db.get_value("Account", payable, "root_type")
        self.assertEqual(rec_root, "Asset")
        self.assertEqual(pay_root, "Liability")

        rec_is_group = frappe.db.get_value("Account", receivable, "is_group")
        pay_is_group = frappe.db.get_value("Account", payable, "is_group")
        self.assertEqual(rec_is_group, 1)
        self.assertEqual(pay_is_group, 1)

    def test_groups_creation_is_idempotent(self):
        inter_branch._ensure_inter_branch_groups(self.company)
        # Second call must not raise
        inter_branch._ensure_inter_branch_groups(self.company)
```

- [ ] **Step 2: Run test to verify it fails**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestInterBranchGroups
```
Expected: AttributeError on `_ensure_inter_branch_groups`.

- [ ] **Step 3: Implement `_ensure_inter_branch_groups` in `rmax_custom/inter_branch.py`**

Add to the module:

```python
INTER_BRANCH_RECEIVABLE_LABEL = "Inter-Branch Receivable"
INTER_BRANCH_PAYABLE_LABEL = "Inter-Branch Payable"


def _company_abbr(company: str) -> str:
    return frappe.db.get_value("Company", company, "abbr")


def _find_parent_group(company: str, root_type: str, fallback_label: str) -> str:
    """Return the canonical parent group account name for a given root_type.

    Asset → "Current Assets - <abbr>" if it exists, else falls back to the
    company's root Asset group. Liability → "Current Liabilities - <abbr>".
    """
    abbr = _company_abbr(company)
    candidate = f"{fallback_label} - {abbr}"
    if frappe.db.exists("Account", candidate):
        return candidate

    # Fallback: the company root for the matching root_type
    root = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": root_type, "is_group": 1, "parent_account": ""},
        "name",
    )
    if not root:
        frappe.throw(_("Cannot locate root {0} group for company {1}").format(root_type, company))
    return root


def _ensure_group_account(company: str, label: str, root_type: str, parent: str) -> str:
    abbr = _company_abbr(company)
    name = f"{label} - {abbr}"
    if frappe.db.exists("Account", name):
        return name

    acc = frappe.new_doc("Account")
    acc.account_name = label
    acc.company = company
    acc.parent_account = parent
    acc.is_group = 1
    acc.root_type = root_type
    if root_type == "Asset":
        acc.account_type = "Receivable"
    elif root_type == "Liability":
        acc.account_type = "Payable"
    acc.insert(ignore_permissions=True)
    return acc.name


def _ensure_inter_branch_groups(company: str) -> tuple[str, str]:
    """Create the two inter-branch parent groups under Current Assets / Current Liabilities."""
    rec_parent = _find_parent_group(company, "Asset", "Current Assets")
    pay_parent = _find_parent_group(company, "Liability", "Current Liabilities")

    receivable = _ensure_group_account(company, INTER_BRANCH_RECEIVABLE_LABEL, "Asset", rec_parent)
    payable = _ensure_group_account(company, INTER_BRANCH_PAYABLE_LABEL, "Liability", pay_parent)
    return receivable, payable
```

Update `setup_inter_branch_foundation` to call it for every Company:

```python
def setup_inter_branch_foundation() -> None:
    """Idempotent entrypoint called from setup.after_migrate."""
    _ensure_branch_accounting_dimension()
    for company_name in frappe.get_all("Company", pluck="name"):
        _ensure_inter_branch_groups(company_name)
```

> Note: ERPNext's `account_type = "Receivable"` and `"Payable"` on group accounts is purely for classification; party-link enforcement does NOT apply to the inter-branch leaves (we'll use blank `account_type` on leaves so JEs need no Party). See Task 4.

- [ ] **Step 4: Run test to verify it passes**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestInterBranchGroups
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/inter_branch.py rmax_custom/test_inter_branch.py
git commit -m "feat(inter-branch): create Inter-Branch Receivable and Payable parent groups per Company"
```

---

### Task 4: Lazy leaf creation per counterparty branch

**Files:**
- Modify: `rmax_custom/inter_branch.py`
- Modify: `rmax_custom/test_inter_branch.py`

- [ ] **Step 1: Write the failing test for `get_or_create_inter_branch_account`**

Append:

```python
class TestLazyLeafCreation(FrappeTestCase):
    def setUp(self):
        self.company = frappe.db.get_value("Company", {}, "name")
        inter_branch._ensure_inter_branch_groups(self.company)

        # Ensure we have at least one Branch to use as counterparty
        if not frappe.db.exists("Branch", "TestBranchAlpha"):
            br = frappe.new_doc("Branch")
            br.branch = "TestBranchAlpha"
            br.insert(ignore_permissions=True)
        self.counterparty = "TestBranchAlpha"

    def test_creates_receivable_leaf(self):
        name = inter_branch.get_or_create_inter_branch_account(
            self.company, self.counterparty, side="receivable"
        )
        self.assertTrue(frappe.db.exists("Account", name))
        is_group = frappe.db.get_value("Account", name, "is_group")
        root_type = frappe.db.get_value("Account", name, "root_type")
        self.assertEqual(is_group, 0)
        self.assertEqual(root_type, "Asset")

    def test_creates_payable_leaf(self):
        name = inter_branch.get_or_create_inter_branch_account(
            self.company, self.counterparty, side="payable"
        )
        self.assertTrue(frappe.db.exists("Account", name))
        root_type = frappe.db.get_value("Account", name, "root_type")
        self.assertEqual(root_type, "Liability")

    def test_lookup_is_idempotent(self):
        first = inter_branch.get_or_create_inter_branch_account(
            self.company, self.counterparty, side="receivable"
        )
        second = inter_branch.get_or_create_inter_branch_account(
            self.company, self.counterparty, side="receivable"
        )
        self.assertEqual(first, second)

    def test_invalid_side_raises(self):
        with self.assertRaises(ValueError):
            inter_branch.get_or_create_inter_branch_account(
                self.company, self.counterparty, side="bogus"
            )
```

- [ ] **Step 2: Run test to verify it fails**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestLazyLeafCreation
```
Expected: AttributeError on `get_or_create_inter_branch_account`.

- [ ] **Step 3: Implement `get_or_create_inter_branch_account`**

Add to `rmax_custom/inter_branch.py`:

```python
def _slug(text: str) -> str:
    """Strip non-alphanumeric chars to keep account name compact."""
    return "".join(ch for ch in text if ch.isalnum() or ch == " ").strip()


def get_or_create_inter_branch_account(
    company: str, counterparty_branch: str, side: str
) -> str:
    """Return the leaf account name for the given counterparty + side.

    side = "receivable" → "Due from <Branch> - <abbr>" under Inter-Branch Receivable group
    side = "payable"    → "Due to <Branch> - <abbr>" under Inter-Branch Payable group

    Creates the account on first call; subsequent calls return the existing name.
    """
    if side not in ("receivable", "payable"):
        raise ValueError(f"side must be 'receivable' or 'payable', got: {side!r}")

    abbr = _company_abbr(company)
    if side == "receivable":
        prefix = "Due from"
        parent = f"{INTER_BRANCH_RECEIVABLE_LABEL} - {abbr}"
        root_type = "Asset"
    else:
        prefix = "Due to"
        parent = f"{INTER_BRANCH_PAYABLE_LABEL} - {abbr}"
        root_type = "Liability"

    if not frappe.db.exists("Account", parent):
        _ensure_inter_branch_groups(company)

    leaf_label = f"{prefix} {_slug(counterparty_branch)}"
    leaf_name = f"{leaf_label} - {abbr}"

    if frappe.db.exists("Account", leaf_name):
        return leaf_name

    company_currency = frappe.db.get_value("Company", company, "default_currency")
    acc = frappe.new_doc("Account")
    acc.account_name = leaf_label
    acc.company = company
    acc.parent_account = parent
    acc.is_group = 0
    acc.root_type = root_type
    # Leaf account_type left blank so JE entries do not require a Party.
    acc.account_currency = company_currency
    acc.insert(ignore_permissions=True)
    return acc.name
```

- [ ] **Step 4: Run test to verify it passes**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestLazyLeafCreation
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/inter_branch.py rmax_custom/test_inter_branch.py
git commit -m "feat(inter-branch): lazy leaf creation per counterparty branch"
```

---

### Task 5: Branch.after_insert — auto-create leaves for new branch

**Files:**
- Modify: `rmax_custom/inter_branch.py`
- Modify: `rmax_custom/test_inter_branch.py`
- Modify: `rmax_custom/hooks.py` (register the hook)

- [ ] **Step 1: Write the failing test**

Append:

```python
class TestBranchAfterInsert(FrappeTestCase):
    def setUp(self):
        self.company = frappe.db.get_value("Company", {}, "name")
        inter_branch._ensure_inter_branch_groups(self.company)

    def test_after_insert_creates_leaves_for_all_existing_branches(self):
        # Seed two existing branches
        for br_name in ("TestExistingA", "TestExistingB"):
            if not frappe.db.exists("Branch", br_name):
                b = frappe.new_doc("Branch")
                b.branch = br_name
                b.insert(ignore_permissions=True)

        # Insert the new branch — its after_insert should create leaves both directions
        new_branch = "TestNewBranch"
        if frappe.db.exists("Branch", new_branch):
            frappe.delete_doc("Branch", new_branch, force=1, ignore_permissions=True)
        b = frappe.new_doc("Branch")
        b.branch = new_branch
        b.insert(ignore_permissions=True)
        # Trigger the hook explicitly in case fixtures don't wire it during tests
        inter_branch.on_branch_insert(b)

        abbr = frappe.db.get_value("Company", self.company, "abbr")
        # New branch must have receivable + payable leaves for each existing branch
        for existing in ("TestExistingA", "TestExistingB"):
            self.assertTrue(
                frappe.db.exists("Account", f"Due from {existing} - {abbr}"),
                f"Missing receivable leaf for existing branch {existing}",
            )
            self.assertTrue(
                frappe.db.exists("Account", f"Due to {existing} - {abbr}"),
                f"Missing payable leaf for existing branch {existing}",
            )
        # And the existing branches now also have leaves pointing at the new branch
        self.assertTrue(frappe.db.exists("Account", f"Due from {new_branch} - {abbr}"))
        self.assertTrue(frappe.db.exists("Account", f"Due to {new_branch} - {abbr}"))
```

- [ ] **Step 2: Run test to verify it fails**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestBranchAfterInsert
```
Expected: AttributeError on `inter_branch.on_branch_insert`.

- [ ] **Step 3: Implement `on_branch_insert`**

Add:

```python
def on_branch_insert(doc, method=None) -> None:
    """Branch.after_insert hook.

    For every Company in the system, create the receivable + payable leaves
    that connect the new branch to every other existing branch. Emits a
    msgprint warning so the operator knows accounts were auto-loaded.
    """
    new_branch = doc.name
    companies = frappe.get_all("Company", pluck="name")

    created: list[str] = []
    for company in companies:
        _ensure_inter_branch_groups(company)
        existing_branches = [
            b for b in frappe.get_all("Branch", pluck="name") if b != new_branch
        ]
        for other in existing_branches:
            for side in ("receivable", "payable"):
                # Leaves on the new branch that reference each existing counterparty
                created.append(get_or_create_inter_branch_account(company, other, side))
                # And reverse: existing branches need leaves referencing the new branch
                created.append(get_or_create_inter_branch_account(company, new_branch, side))

    frappe.msgprint(
        _(
            "Inter-Branch account heads have been auto-loaded for branch <b>{0}</b>. "
            "Verify the Chart of Accounts before posting transactions."
        ).format(new_branch),
        title=_("Inter-Branch Accounts Created"),
        indicator="orange",
    )
```

- [ ] **Step 4: Register the hook in `rmax_custom/hooks.py`**

Inside the existing `doc_events` block, add a `Branch` entry. Find the existing `doc_events = {` dict and add:

```python
"Branch": {
    "after_insert": "rmax_custom.inter_branch.on_branch_insert",
},
```

- [ ] **Step 5: Run test to verify it passes**

```
sudo -u v15 bench --site rmax_dev2 clear-cache
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestBranchAfterInsert
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rmax_custom/inter_branch.py rmax_custom/test_inter_branch.py rmax_custom/hooks.py
git commit -m "feat(inter-branch): auto-create leaves on Branch insert"
```

---

### Task 6: Self-balancing JE auto-injector — happy path (2 branches)

**Files:**
- Modify: `rmax_custom/inter_branch.py`
- Modify: `rmax_custom/test_inter_branch.py`

- [ ] **Step 1: Write the failing test for the simple 2-branch case**

Append:

```python
class TestAutoInjector(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.db.get_value("Company", {}, "name")
        inter_branch._ensure_inter_branch_groups(cls.company)
        cls.abbr = frappe.db.get_value("Company", cls.company, "abbr")

        # Ensure cut-over date so injector applies
        frappe.db.set_value(
            "Company", cls.company, "custom_inter_branch_cut_over_date", "2026-01-01"
        )

        for br in ("HO", "Riyadh"):
            if not frappe.db.exists("Branch", br):
                d = frappe.new_doc("Branch")
                d.branch = br
                d.insert(ignore_permissions=True)

    def _make_je_template(self, posting_date: str = "2026-04-28") -> "frappe.model.document.Document":
        """Build an UNSAVED Journal Entry that posts rent in Riyadh paid by HO bank."""
        # Resolve generic accounts that exist on test company
        rent_acc = frappe.db.get_value(
            "Account", {"company": self.company, "is_group": 0, "root_type": "Expense"}, "name"
        )
        bank_acc = frappe.db.get_value(
            "Account", {"company": self.company, "account_type": "Bank", "is_group": 0}, "name"
        )
        self.assertIsNotNone(rent_acc)
        self.assertIsNotNone(bank_acc)

        je = frappe.new_doc("Journal Entry")
        je.posting_date = posting_date
        je.company = self.company
        je.voucher_type = "Journal Entry"
        je.append(
            "accounts",
            {"account": rent_acc, "debit_in_account_currency": 1000, "branch": "Riyadh"},
        )
        je.append(
            "accounts",
            {"account": bank_acc, "credit_in_account_currency": 1000, "branch": "HO"},
        )
        return je

    def test_two_branch_imbalance_gets_injected(self):
        je = self._make_je_template()
        inter_branch.auto_inject_inter_branch_legs(je)

        injected = [row for row in je.accounts if getattr(row, "custom_auto_inserted", 0)]
        self.assertEqual(len(injected), 2, f"Expected 2 injected legs, got: {injected}")

        # Per-branch balance check after injection
        per_branch: dict[str, float] = {}
        for row in je.accounts:
            br = row.branch or ""
            per_branch[br] = per_branch.get(br, 0.0) + flt(row.debit_in_account_currency) - flt(row.credit_in_account_currency)
        for br, bal in per_branch.items():
            self.assertEqual(round(bal, 2), 0.0, f"Branch {br} unbalanced: {bal}")

    def test_three_branch_je_rejected(self):
        je = self._make_je_template()
        # Add a third branch line to force ambiguity
        rent_acc = je.accounts[0].account
        je.append(
            "accounts",
            {"account": rent_acc, "debit_in_account_currency": 500, "branch": "Jeddah"},
        )
        # Make the entry totals match (debit side now 1500, credit still 1000)
        je.accounts[1].credit_in_account_currency = 1500

        if not frappe.db.exists("Branch", "Jeddah"):
            d = frappe.new_doc("Branch")
            d.branch = "Jeddah"
            d.insert(ignore_permissions=True)

        with self.assertRaises(frappe.ValidationError):
            inter_branch.auto_inject_inter_branch_legs(je)

    def test_pre_cutover_je_skipped(self):
        je = self._make_je_template(posting_date="2025-01-01")
        inter_branch.auto_inject_inter_branch_legs(je)
        injected = [row for row in je.accounts if getattr(row, "custom_auto_inserted", 0)]
        self.assertEqual(injected, [])

    def test_balanced_single_branch_untouched(self):
        rent_acc = frappe.db.get_value(
            "Account", {"company": self.company, "is_group": 0, "root_type": "Expense"}, "name"
        )
        bank_acc = frappe.db.get_value(
            "Account", {"company": self.company, "account_type": "Bank", "is_group": 0}, "name"
        )
        je = frappe.new_doc("Journal Entry")
        je.posting_date = "2026-04-28"
        je.company = self.company
        je.append(
            "accounts",
            {"account": rent_acc, "debit_in_account_currency": 100, "branch": "Riyadh"},
        )
        je.append(
            "accounts",
            {"account": bank_acc, "credit_in_account_currency": 100, "branch": "Riyadh"},
        )
        inter_branch.auto_inject_inter_branch_legs(je)
        injected = [row for row in je.accounts if getattr(row, "custom_auto_inserted", 0)]
        self.assertEqual(injected, [])

    def test_idempotent_on_repeat_validate(self):
        je = self._make_je_template()
        inter_branch.auto_inject_inter_branch_legs(je)
        first_count = len(je.accounts)
        inter_branch.auto_inject_inter_branch_legs(je)
        self.assertEqual(len(je.accounts), first_count, "Re-running injector duplicated legs")
```

- [ ] **Step 2: Run tests to verify they fail**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestAutoInjector
```
Expected: AttributeError on `auto_inject_inter_branch_legs`.

- [ ] **Step 3: Implement the auto-injector**

Add to `rmax_custom/inter_branch.py`:

```python
def _per_branch_imbalance(je) -> dict[str, float]:
    """Return {branch: signed_imbalance}; positive = excess debit, negative = excess credit."""
    totals: dict[str, float] = {}
    for row in je.accounts or []:
        br = (row.branch or "").strip()
        if not br:
            continue
        totals[br] = totals.get(br, 0.0) + flt(row.debit_in_account_currency) - flt(
            row.credit_in_account_currency
        )
    # Drop near-zero entries (rounding tolerance: 0.01)
    return {br: round(v, 2) for br, v in totals.items() if abs(v) >= 0.01}


def _is_pre_cut_over(je) -> bool:
    cut_over = frappe.db.get_value(
        "Company", je.company, "custom_inter_branch_cut_over_date"
    )
    if not cut_over:
        # No cut-over configured = injector disabled for this company
        return True
    return getdate(je.posting_date) < getdate(cut_over)


def _strip_existing_auto_legs(je) -> None:
    """Remove any prior auto-injected rows so we can recompute idempotently."""
    je.accounts = [
        row for row in (je.accounts or []) if not getattr(row, "custom_auto_inserted", 0)
    ]


def auto_inject_inter_branch_legs(doc, method=None) -> None:
    """Journal Entry.validate hook.

    If the JE touches multiple branches and per-branch debits ≠ credits,
    inject `Inter-Branch — <other>` balancing legs so each branch zeroes.
    """
    if doc.doctype != "Journal Entry":
        return
    if not doc.company:
        return
    if _is_pre_cut_over(doc):
        return

    _strip_existing_auto_legs(doc)
    imbalance = _per_branch_imbalance(doc)

    if not imbalance:
        return

    if len(imbalance) > 2:
        frappe.throw(
            _(
                "Inter-Branch auto-injection supports exactly two branches per Journal Entry, "
                "but this entry touches: <b>{0}</b>. "
                "Please split into separate Journal Entries — one per branch pair."
            ).format(", ".join(sorted(imbalance))),
            title=_("Multi-Branch Journal Entry Not Supported"),
        )

    if len(imbalance) < 2:
        # Single branch is unbalanced → standard JE validation will catch it
        return

    branch_a, branch_b = sorted(imbalance.keys())
    delta_a = imbalance[branch_a]
    delta_b = imbalance[branch_b]

    # Sanity: combined debits = combined credits, so deltas must sum to zero
    if round(delta_a + delta_b, 2) != 0:
        frappe.throw(
            _(
                "Journal Entry totals are unbalanced before inter-branch injection: "
                "Branch {0} delta = {1}, Branch {2} delta = {3}."
            ).format(branch_a, delta_a, branch_b, delta_b),
            title=_("Unbalanced Journal Entry"),
        )

    # branch_a's excess debit (delta_a > 0) means branch_a has received value owed by branch_b.
    # → Credit Inter-Branch—B on branch_a's side; Debit Inter-Branch—A on branch_b's side.
    # Side classification follows: when branch_a is the borrower (delta_a > 0 means it consumed
    # value paid by branch_b's bank), branch_a credits "Due to branch_b" (Liability), and branch_b
    # debits "Due from branch_a" (Asset).
    if delta_a > 0:
        debtor, creditor = branch_a, branch_b
        amount = delta_a
    else:
        debtor, creditor = branch_b, branch_a
        amount = delta_b

    # Inject TWO legs into the same JE — one per branch perspective
    debtor_payable = get_or_create_inter_branch_account(doc.company, creditor, side="payable")
    creditor_receivable = get_or_create_inter_branch_account(doc.company, debtor, side="receivable")

    source_doctype = ""
    source_docname = ""
    # If the JE was generated by another doc (e.g. Stock Transfer companion), it pre-stamps
    # accounts[0].custom_source_doctype. Reuse those values for the injected legs.
    for row in doc.accounts:
        if getattr(row, "custom_source_doctype", None):
            source_doctype = row.custom_source_doctype
            source_docname = row.custom_source_docname or ""
            break

    doc.append(
        "accounts",
        {
            "account": debtor_payable,
            "credit_in_account_currency": amount,
            "branch": debtor,
            "custom_auto_inserted": 1,
            "custom_source_doctype": source_doctype or "Journal Entry",
            "custom_source_docname": source_docname or doc.name or "",
            "user_remark": _("Auto-injected: {0} owes {1}").format(debtor, creditor),
        },
    )
    doc.append(
        "accounts",
        {
            "account": creditor_receivable,
            "debit_in_account_currency": amount,
            "branch": creditor,
            "custom_auto_inserted": 1,
            "custom_source_doctype": source_doctype or "Journal Entry",
            "custom_source_docname": source_docname or doc.name or "",
            "user_remark": _("Auto-injected: {0} receivable from {1}").format(creditor, debtor),
        },
    )

    # Final guard — re-compute and assert all branches balance
    final = _per_branch_imbalance(doc)
    if final:
        frappe.throw(
            _("Auto-injection failed to balance branches: {0}").format(final),
            title=_("Inter-Branch Auto-Injection Error"),
        )
```

- [ ] **Step 4: Register the validate hook**

In `rmax_custom/hooks.py`, add inside `doc_events`:

```python
"Journal Entry": {
    "validate": "rmax_custom.inter_branch.auto_inject_inter_branch_legs",
},
```

If `Journal Entry` already exists in `doc_events`, append `validate` to its dict instead of replacing.

- [ ] **Step 5: Run tests to verify they pass**

```
sudo -u v15 bench --site rmax_dev2 clear-cache
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestAutoInjector
```
Expected: all five tests PASS.

- [ ] **Step 6: Commit**

```bash
git add rmax_custom/inter_branch.py rmax_custom/test_inter_branch.py rmax_custom/hooks.py
git commit -m "feat(inter-branch): self-balancing JE auto-injector with cut-over guard"
```

---

### Task 7: End-to-end JE submission test (HO pays rent for Riyadh)

**Files:**
- Modify: `rmax_custom/test_inter_branch.py`

- [ ] **Step 1: Write the failing test that submits a real JE**

Append:

```python
class TestRentScenarioE2E(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.db.get_value("Company", {}, "name")
        inter_branch._ensure_inter_branch_groups(cls.company)
        frappe.db.set_value(
            "Company", cls.company, "custom_inter_branch_cut_over_date", "2026-01-01"
        )
        for br in ("HO", "Riyadh"):
            if not frappe.db.exists("Branch", br):
                d = frappe.new_doc("Branch")
                d.branch = br
                d.insert(ignore_permissions=True)
        # Force leaves to exist
        inter_branch.get_or_create_inter_branch_account(cls.company, "HO", "receivable")
        inter_branch.get_or_create_inter_branch_account(cls.company, "HO", "payable")
        inter_branch.get_or_create_inter_branch_account(cls.company, "Riyadh", "receivable")
        inter_branch.get_or_create_inter_branch_account(cls.company, "Riyadh", "payable")

    def test_rent_paid_by_ho_for_riyadh_books_correctly(self):
        rent_acc = frappe.db.get_value(
            "Account", {"company": self.company, "is_group": 0, "root_type": "Expense"}, "name"
        )
        bank_acc = frappe.db.get_value(
            "Account", {"company": self.company, "account_type": "Bank", "is_group": 0}, "name"
        )
        je = frappe.new_doc("Journal Entry")
        je.posting_date = "2026-04-28"
        je.company = self.company
        je.voucher_type = "Journal Entry"
        je.append(
            "accounts",
            {"account": rent_acc, "debit_in_account_currency": 1000, "branch": "Riyadh"},
        )
        je.append(
            "accounts",
            {"account": bank_acc, "credit_in_account_currency": 1000, "branch": "HO"},
        )
        je.insert(ignore_permissions=True)
        je.submit()

        je.reload()
        # Expect 4 lines after injection
        self.assertEqual(len(je.accounts), 4)
        injected = [r for r in je.accounts if r.custom_auto_inserted]
        self.assertEqual(len(injected), 2)

        # GL entries balance per-branch
        gl_rows = frappe.get_all(
            "GL Entry",
            filters={"voucher_no": je.name, "is_cancelled": 0},
            fields=["branch", "debit", "credit"],
        )
        per_branch: dict[str, float] = {}
        for r in gl_rows:
            per_branch[r.branch] = per_branch.get(r.branch, 0.0) + flt(r.debit) - flt(r.credit)
        for br, bal in per_branch.items():
            self.assertEqual(round(bal, 2), 0.0, f"Branch {br} GL not balanced: {bal}")
```

- [ ] **Step 2: Run test to verify behavior**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestRentScenarioE2E
```
Expected: PASS (the implementation from Task 6 should already cover this).

If it fails: investigate whether ERPNext's standard JE validation rejects the injected legs (e.g. account_currency mismatch). Adjust injector to copy `account_currency` from the leaf account.

- [ ] **Step 3: Commit**

```bash
git add rmax_custom/test_inter_branch.py
git commit -m "test(inter-branch): end-to-end rent scenario submits and balances per-branch"
```

---

### Task 8: Branch resolver helper (Warehouse → Branch)

**Files:**
- Modify: `rmax_custom/inter_branch.py`
- Modify: `rmax_custom/test_inter_branch.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
class TestBranchResolver(FrappeTestCase):
    def test_resolves_warehouse_via_branch_configuration(self):
        # Test environment seeded with at least one Branch Configuration mapping
        sample = frappe.db.sql(
            """
            SELECT bcw.warehouse, bc.branch
            FROM `tabBranch Configuration Warehouse` bcw
            INNER JOIN `tabBranch Configuration` bc ON bc.name = bcw.parent
            WHERE bcw.warehouse IS NOT NULL AND bc.branch IS NOT NULL
            LIMIT 1
            """,
            as_dict=True,
        )
        if not sample:
            self.skipTest("No Branch Configuration → Warehouse mapping in test data")
        wh, expected_branch = sample[0].warehouse, sample[0].branch
        self.assertEqual(inter_branch.resolve_warehouse_branch(wh), expected_branch)

    def test_unmapped_warehouse_returns_none(self):
        self.assertIsNone(inter_branch.resolve_warehouse_branch("NonExistentWH-XYZ"))
```

- [ ] **Step 2: Run test to verify it fails**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestBranchResolver
```
Expected: AttributeError on `resolve_warehouse_branch`.

- [ ] **Step 3: Implement the resolver**

Add to `rmax_custom/inter_branch.py`:

```python
def resolve_warehouse_branch(warehouse: str) -> str | None:
    """Look up the Branch linked to a warehouse via Branch Configuration.

    Returns None when no mapping exists. The first matching mapping wins
    (multiple Branch Configurations could reference the same warehouse —
    in RMAX this is rare and indicates shared-warehouse setups).
    """
    if not warehouse:
        return None
    rows = frappe.db.sql(
        """
        SELECT bc.branch
        FROM `tabBranch Configuration Warehouse` bcw
        INNER JOIN `tabBranch Configuration` bc ON bc.name = bcw.parent
        WHERE bcw.warehouse = %s AND bc.branch IS NOT NULL
        ORDER BY bc.modified DESC
        LIMIT 1
        """,
        (warehouse,),
    )
    return rows[0][0] if rows else None
```

- [ ] **Step 4: Run test to verify it passes**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestBranchResolver
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/inter_branch.py rmax_custom/test_inter_branch.py
git commit -m "feat(inter-branch): warehouse-to-branch resolver via Branch Configuration"
```

---

### Task 9: Stock Transfer companion JE (cross-branch detection)

**Files:**
- Modify: `rmax_custom/inter_branch.py`
- Modify: `rmax_custom/rmax_custom/doctype/stock_transfer/stock_transfer.py:127-134`
- Modify: `rmax_custom/test_inter_branch.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
class TestStockTransferCompanionJE(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.db.get_value("Company", {}, "name")
        inter_branch._ensure_inter_branch_groups(cls.company)
        frappe.db.set_value(
            "Company", cls.company, "custom_inter_branch_cut_over_date", "2026-01-01"
        )

    def test_returns_none_when_warehouses_in_same_branch(self):
        # Build a Stock Transfer doc-like stub with same source/target branch
        class Stub:
            name = "ST-TEST-SAME"
            company = self.company
            set_source_warehouse = "WH1"
            set_target_warehouse = "WH2"
            posting_date = "2026-04-28"

        # Force resolver to return the same branch for both
        original = inter_branch.resolve_warehouse_branch
        inter_branch.resolve_warehouse_branch = lambda wh: "Riyadh"
        try:
            result = inter_branch.create_companion_inter_branch_je_for_stock_transfer(Stub())
            self.assertIsNone(result)
        finally:
            inter_branch.resolve_warehouse_branch = original

    def test_creates_companion_je_when_branches_differ(self):
        # Find a real cross-branch warehouse pair
        rows = frappe.db.sql(
            """
            SELECT bcw.warehouse, bc.branch
            FROM `tabBranch Configuration Warehouse` bcw
            INNER JOIN `tabBranch Configuration` bc ON bc.name = bcw.parent
            WHERE bc.branch IS NOT NULL
            """,
            as_dict=True,
        )
        if len(rows) < 2 or len({r.branch for r in rows}) < 2:
            self.skipTest("Need at least two warehouses in different branches to run this test")

        # Pick one from branch A and one from branch B
        by_branch: dict[str, list[str]] = {}
        for r in rows:
            by_branch.setdefault(r.branch, []).append(r.warehouse)
        branches = [b for b, whs in by_branch.items() if whs]
        source_branch, target_branch = branches[0], branches[1]
        source_wh = by_branch[source_branch][0]
        target_wh = by_branch[target_branch][0]

        # Build a stub Stock Transfer
        class Stub:
            pass

        stub = Stub()
        stub.name = "ST-TEST-CROSS"
        stub.company = self.company
        stub.set_source_warehouse = source_wh
        stub.set_target_warehouse = target_wh
        stub.posting_date = "2026-04-28"
        stub.items = []
        # Fake one item line with valuation
        item = type("ItemRow", (), {})()
        item.item_code = "TestItem"
        item.basic_amount = 500
        item.qty = 1
        stub.items.append(item)

        je_name = inter_branch.create_companion_inter_branch_je_for_stock_transfer(stub)
        self.assertIsNotNone(je_name, "Expected companion JE to be created for cross-branch transfer")
        je = frappe.get_doc("Journal Entry", je_name)
        self.assertEqual(je.docstatus, 1)
        # Sanity: branches balance
        per_branch: dict[str, float] = {}
        for row in je.accounts:
            per_branch[row.branch] = per_branch.get(row.branch, 0.0) + flt(row.debit_in_account_currency) - flt(row.credit_in_account_currency)
        for br, bal in per_branch.items():
            self.assertEqual(round(bal, 2), 0.0)
        # Source traceability
        sourced = [r for r in je.accounts if r.custom_source_doctype == "Stock Transfer"]
        self.assertEqual(len(sourced), len(je.accounts))
```

- [ ] **Step 2: Run test to verify it fails**

```
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestStockTransferCompanionJE
```
Expected: AttributeError on `create_companion_inter_branch_je_for_stock_transfer`.

- [ ] **Step 3: Implement the companion JE creator**

Add to `rmax_custom/inter_branch.py`:

```python
def _stock_transfer_total_value(stock_transfer) -> float:
    """Sum the basic_amount across items; falls back to qty * basic_rate when needed."""
    total = 0.0
    for item in stock_transfer.items or []:
        amt = flt(getattr(item, "basic_amount", 0))
        if not amt:
            amt = flt(getattr(item, "qty", 0)) * flt(getattr(item, "basic_rate", 0))
        total += amt
    return round(total, 2)


def create_companion_inter_branch_je_for_stock_transfer(stock_transfer) -> str | None:
    """Create a 2-line Journal Entry that records the inter-branch obligation
    arising from a cross-branch Stock Transfer at valuation cost.

    Returns the new JE name, or None if no JE was needed (same-branch transfer).

    Posts:
        Dr Inter-Branch—<source>  (branch = <target>)
        Cr Inter-Branch—<target>  (branch = <source>)
    The auto-injector is NOT involved — this JE is born self-balancing per-branch only
    because the underlying Stock Entry's own GL contributes the offsetting Stock-in-Hand
    legs. To reflect that, the companion JE is structured so that EACH branch shows a
    one-sided line balanced ONLY when combined with the Stock Entry. The validator must
    NOT auto-inject — to avoid that we mark the rows custom_auto_inserted=1 so the
    injector ignores them on subsequent re-validations.
    """
    source_wh = getattr(stock_transfer, "set_source_warehouse", None)
    target_wh = getattr(stock_transfer, "set_target_warehouse", None)
    source_branch = resolve_warehouse_branch(source_wh)
    target_branch = resolve_warehouse_branch(target_wh)

    if not source_branch or not target_branch:
        return None
    if source_branch == target_branch:
        return None

    amount = _stock_transfer_total_value(stock_transfer)
    if amount <= 0:
        return None

    company = stock_transfer.company

    # Account selection:
    # - Source branch books a RECEIVABLE from target (Asset increase, debit)
    # - Target branch books a PAYABLE to source (Liability increase, credit)
    src_receivable = get_or_create_inter_branch_account(company, target_branch, "receivable")
    tgt_payable = get_or_create_inter_branch_account(company, source_branch, "payable")

    je = frappe.new_doc("Journal Entry")
    je.posting_date = stock_transfer.posting_date
    je.company = company
    je.voucher_type = "Journal Entry"
    je.user_remark = _("Inter-Branch obligation from Stock Transfer {0}").format(
        stock_transfer.name
    )
    je.append(
        "accounts",
        {
            "account": src_receivable,
            "debit_in_account_currency": amount,
            "branch": source_branch,
            "custom_auto_inserted": 1,
            "custom_source_doctype": "Stock Transfer",
            "custom_source_docname": stock_transfer.name,
        },
    )
    je.append(
        "accounts",
        {
            "account": tgt_payable,
            "credit_in_account_currency": amount,
            "branch": target_branch,
            "custom_auto_inserted": 1,
            "custom_source_doctype": "Stock Transfer",
            "custom_source_docname": stock_transfer.name,
        },
    )
    # Skip our own injector on this JE — it's already balanced as a unit (debit = credit).
    je.flags.skip_inter_branch_injection = True
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name
```

Update `auto_inject_inter_branch_legs` to honour the skip flag — modify the early-return block:

```python
def auto_inject_inter_branch_legs(doc, method=None) -> None:
    if doc.doctype != "Journal Entry":
        return
    if doc.flags.get("skip_inter_branch_injection"):
        return
    if not doc.company:
        return
    if _is_pre_cut_over(doc):
        return
    # ...rest unchanged...
```

- [ ] **Step 4: Wire the hook into Stock Transfer**

Edit `rmax_custom/rmax_custom/doctype/stock_transfer/stock_transfer.py` `on_submit` (lines 127-134) to:

```python
	def on_submit(self):
		"""Run only when document is submitted (docstatus = 1)"""
		if self.workflow_state != "Approved":
			return

		self.create_stock_entry()
		self._update_material_request_status()

		# Inter-Branch companion JE — only when source and target branches differ
		from rmax_custom import inter_branch
		try:
			inter_branch.create_companion_inter_branch_je_for_stock_transfer(self)
		except Exception:
			frappe.log_error(
				title="Inter-Branch companion JE failed",
				message=frappe.get_traceback(),
			)
			# Re-raise so operator sees the error and the Stock Transfer rolls back.
			raise
```

- [ ] **Step 5: Run tests to verify they pass**

```
sudo -u v15 bench --site rmax_dev2 clear-cache
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.test_inter_branch --test TestStockTransferCompanionJE
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rmax_custom/inter_branch.py rmax_custom/rmax_custom/doctype/stock_transfer/stock_transfer.py rmax_custom/test_inter_branch.py
git commit -m "feat(inter-branch): companion JE on Stock Transfer for cross-branch movements"
```

---

### Task 10: Wire `setup_inter_branch_foundation` into `after_migrate`

**Files:**
- Modify: `rmax_custom/setup.py`

- [ ] **Step 1: Inspect existing `after_migrate` structure**

```bash
grep -n 'def after_migrate\|def setup\|def preserve' rmax_custom/setup.py | head
```

- [ ] **Step 2: Add the call**

In `rmax_custom/setup.py`, locate `def after_migrate():` and add at the end:

```python
def after_migrate():
    # ... existing calls ...

    # Inter-Branch R/P Foundation — Phase 1
    from rmax_custom import inter_branch
    try:
        inter_branch.setup_inter_branch_foundation()
    except Exception:
        frappe.log_error(
            title="Inter-Branch foundation setup failed",
            message=frappe.get_traceback(),
        )
        # Do not raise — after_migrate must be tolerant so other setup runs.
```

- [ ] **Step 3: Run after_migrate manually to verify**

```
sudo -u v15 bench --site rmax_dev2 execute rmax_custom.setup.after_migrate
```
Expected: returns without error. Verify Inter-Branch group accounts exist for the test Company:
```
sudo -u v15 bench --site rmax_dev2 execute 'frappe.db.exists' --kwargs '{"doctype": "Account", "filters": {"account_name": "Inter-Branch Receivable"}}'
```
Expected: returns the account name.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/setup.py
git commit -m "feat(inter-branch): wire foundation setup into after_migrate"
```

---

### Task 11: Inter-Branch Reconciliation script report

**Files:**
- Create: `rmax_custom/rmax_custom/report/inter_branch_reconciliation/__init__.py`
- Create: `rmax_custom/rmax_custom/report/inter_branch_reconciliation/inter_branch_reconciliation.json`
- Create: `rmax_custom/rmax_custom/report/inter_branch_reconciliation/inter_branch_reconciliation.py`
- Create: `rmax_custom/rmax_custom/report/inter_branch_reconciliation/inter_branch_reconciliation.js`

- [ ] **Step 1: Create the empty `__init__.py`**

Create `rmax_custom/rmax_custom/report/inter_branch_reconciliation/__init__.py` as an empty file.

- [ ] **Step 2: Create the report metadata JSON**

Create `inter_branch_reconciliation.json`:

```json
{
 "add_total_row": 1,
 "creation": "2026-04-28 00:00:00.000000",
 "disable_prepared_report": 0,
 "disabled": 0,
 "docstatus": 0,
 "doctype": "Report",
 "is_standard": "Yes",
 "letter_head": null,
 "modified": "2026-04-28 00:00:00.000000",
 "module": "Rmax Custom",
 "name": "Inter-Branch Reconciliation",
 "owner": "Administrator",
 "prepared_report": 0,
 "ref_doctype": "GL Entry",
 "report_name": "Inter-Branch Reconciliation",
 "report_type": "Script Report",
 "roles": [
  {"role": "Accounts Manager"},
  {"role": "Accounts User"},
  {"role": "Auditor"},
  {"role": "System Manager"}
 ]
}
```

- [ ] **Step 3: Create the report Python**

Create `inter_branch_reconciliation.py`:

```python
"""Inter-Branch Reconciliation report.

Matrix view of inter-branch balances. For every from-branch (rows) and
to-branch (columns), shows the net balance owed. Healthy state: each pair
(A→B and B→A) should sum to zero; non-zero diagonal pairs flag a missing
counterparty tag, an unbalanced manual JE, or a timing difference.
"""
from __future__ import annotations

import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    company = filters.get("company") or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw("Please select a Company filter.")

    abbr = frappe.db.get_value("Company", company, "abbr")
    branches = sorted(b.name for b in frappe.get_all("Branch"))

    # Pull all GL entries posting to inter-branch accounts within the date range
    conds = ["company = %(company)s", "is_cancelled = 0"]
    params: dict = {"company": company, "abbr": f"% - {abbr}"}
    if filters.get("from_date"):
        conds.append("posting_date >= %(from_date)s")
        params["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conds.append("posting_date <= %(to_date)s")
        params["to_date"] = filters["to_date"]

    rows = frappe.db.sql(
        f"""
        SELECT account, branch, SUM(debit) AS dr, SUM(credit) AS cr
        FROM `tabGL Entry`
        WHERE {' AND '.join(conds)}
          AND (account LIKE 'Due from %%' OR account LIKE 'Due to %%')
          AND account LIKE %(abbr)s
        GROUP BY account, branch
        """,
        params,
        as_dict=True,
    )

    # matrix[from_branch][to_branch] = net (debit - credit) on inter-branch leaves
    matrix: dict[str, dict[str, float]] = {b: {b2: 0.0 for b2 in branches} for b in branches}
    for r in rows:
        # Account name format: "Due from <Counterparty> - <abbr>" or "Due to <Counterparty> - <abbr>"
        acct = r.account
        if not acct.endswith(f" - {abbr}"):
            continue
        body = acct[: -(len(abbr) + 3)]  # strip " - <abbr>"
        if body.startswith("Due from "):
            counterparty = body[len("Due from ") :]
        elif body.startswith("Due to "):
            counterparty = body[len("Due to ") :]
        else:
            continue
        owner_branch = r.branch
        if not owner_branch or counterparty not in matrix or owner_branch not in matrix:
            continue
        matrix[owner_branch][counterparty] += flt(r.dr) - flt(r.cr)

    columns = [{"label": "From \\ To", "fieldname": "from_branch", "fieldtype": "Data", "width": 180}]
    for b in branches:
        columns.append({"label": b, "fieldname": _safe_field(b), "fieldtype": "Currency", "width": 140})

    data = []
    for b in branches:
        row = {"from_branch": b}
        for b2 in branches:
            row[_safe_field(b2)] = matrix[b][b2]
        data.append(row)

    return columns, data


def _safe_field(branch_name: str) -> str:
    return "br_" + "".join(ch for ch in branch_name.lower() if ch.isalnum())
```

- [ ] **Step 4: Create the report JS for filters**

Create `inter_branch_reconciliation.js`:

```javascript
frappe.query_reports["Inter-Branch Reconciliation"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
```

- [ ] **Step 5: Reload and run the report**

```
sudo -u v15 bench --site rmax_dev2 execute frappe.reload_doc --kwargs '{"module": "Rmax Custom", "dt": "report", "dn": "inter_branch_reconciliation"}'
sudo -u v15 bench --site rmax_dev2 clear-cache
```
Open the report in the desk UI and confirm it loads. Verify diagonal-opposite cells sum to zero on the matrix (e.g. cell `Riyadh→HO` plus cell `HO→Riyadh` should equal 0 if all entries are balanced).

- [ ] **Step 6: Commit**

```bash
git add rmax_custom/rmax_custom/report/inter_branch_reconciliation/
git commit -m "feat(inter-branch): reconciliation matrix script report"
```

---

### Task 12: Manual smoke test on rmax_dev2

**Goal:** Walk through the four canonical scenarios in the live UI before declaring Phase 1 complete.

- [ ] **Step 1: Configure the cut-over date on the Company**

Open the Company doctype in the desk, set `Inter-Branch Cut-Over Date` to today's date.

- [ ] **Step 2: Verify the Chart of Accounts shows the two new groups**

Navigate to Chart of Accounts. Under Current Assets confirm `Inter-Branch Receivable` exists (Group). Under Current Liabilities confirm `Inter-Branch Payable` exists (Group).

- [ ] **Step 3: Smoke test — Cash transfer (Scenario B)**

Create a Journal Entry:
- Posting Date: today
- Company: rmax_dev2 default
- Line 1: `Bank Account - <abbr>`, Credit 5000, Branch=HO
- Line 2: `Bank Account - <abbr>` (a different bank under Riyadh's control if available — otherwise a clearing fund), Debit 5000, Branch=Riyadh

Save → expect 4 lines after auto-injection (the 2 you entered + 2 inter-branch). Submit → confirm GL Entry view in the JE shows per-branch zeros.

- [ ] **Step 4: Smoke test — Rent paid by HO (Scenario A)**

Create a Journal Entry:
- Line 1: `Rent Expense - <abbr>`, Debit 1000, Branch=Riyadh
- Line 2: `Bank Account - <abbr>`, Credit 1000, Branch=HO

Save → 4 lines, submit. Confirm `Inter-Branch Reconciliation` report now shows HO→Riyadh and Riyadh→HO entries that sum to zero.

- [ ] **Step 5: Smoke test — Cross-branch Stock Transfer (Scenario C)**

Use existing Stock Transfer workflow (MR → ST → approve). Pick a source warehouse in one branch and a target warehouse in another. After approval, look for the auto-created Journal Entry with `custom_source_doctype = "Stock Transfer"` and `custom_source_docname = ST-XXXX`. Confirm Reconciliation report's matrix updates accordingly.

- [ ] **Step 6: Smoke test — Multi-branch JE rejection**

Try to create a JE with three different branches across lines. Save should fail with the explicit "Multi-Branch Journal Entry Not Supported" error.

- [ ] **Step 7: Document smoke test results**

Append a short status note (date + observations) into `RMAX-Custom/docs/superpowers/specs/2026-04-28-inter-branch-rp-phase1-status.md` (create if absent).

- [ ] **Step 8: Commit any cleanup**

```bash
git add -A docs/superpowers/specs/
git commit -m "docs(inter-branch): smoke-test results for Phase 1 on rmax_dev2"
```

---

### Task 13: Deploy to rmax_dev2

**Files:** none (deployment commands only)

- [ ] **Step 1: Push to GitHub main**

```bash
git push origin main
```

- [ ] **Step 2: Pull and migrate on RMAX server**

Use the Server Manager API documented in CLAUDE.md (or SSH into the RMAX server):

```bash
# Pull
curl -s -X POST -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command": "cd /home/v15/frappe-bench/apps/rmax_custom && sudo -u v15 git pull upstream main"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command

# Migrate
curl -s -X POST -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command": "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 migrate"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command

# Clear cache + reload
curl -s -X POST -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command": "cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command
```

- [ ] **Step 3: Verify on dev URL**

Open `https://rmax-dev.fateherp.com`, log in as Administrator, repeat the smoke tests from Task 12 in the production-like environment.

- [ ] **Step 4: Tag the release**

```bash
git tag -a phase1-inter-branch-rp -m "Phase 1: Inter-Branch Receivables & Payables foundation"
git push origin phase1-inter-branch-rp
```

> **Do not deploy to UAT yet.** Soak on dev first; deferred to a separate UAT plan once stable.

---

## Self-Review Checklist (run before declaring complete)

1. **Spec coverage:**
   - Branch as mandatory accounting dimension → Task 2
   - Chart of accounts (Inter-Branch R + P groups) → Task 3
   - Lazy leaf creation per counterparty → Task 4
   - Auto-load on new Branch + warn → Task 5
   - Self-balancing JE auto-injector → Task 6
   - Source traceability fields → Task 1 + injector populates them
   - Stock Transfer cross-branch → Task 8 + Task 9
   - Reconciliation report → Task 11
   - Cut-over date guard → Task 1 + Task 6
   - Three-branch rejection → Task 6 test
   - End-to-end rent scenario → Task 7

2. **Out of scope (verified deferred):** Settlement / Clearing / Salary / Expense Claim / Vendor-on-behalf / Branch-wise TB-P&L-BS / HO overhead allocation. None of these tasks touch those areas.

3. **Critical guardrails:**
   - No DocPerm changes → no permission preservation needed
   - All schema changes idempotent → Tasks 1, 2, 3, 4, 10
   - Cut-over date prevents historical injection → Task 6
   - Account currency set at creation → Task 4

4. **Type / signature consistency check:**
   - `_ensure_inter_branch_groups(company)` returns `tuple[str, str]` → consistent across Tasks 3, 4, 5
   - `get_or_create_inter_branch_account(company, counterparty_branch, side)` signature consistent across Tasks 4, 5, 6, 9
   - `resolve_warehouse_branch(warehouse) -> str | None` consistent across Tasks 8, 9
   - `auto_inject_inter_branch_legs(doc, method=None)` signature matches Frappe doc_events convention

---

## Plan complete and saved.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
