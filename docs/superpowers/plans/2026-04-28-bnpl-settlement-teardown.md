# BNPL Settlement Teardown + JE Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the BNPL Settlement DocType + child + Pending Settlement report; replace with a Journal Entry button that loads Tabby/Tamara settlement account heads, warns on clearing-account overdraw, leaves submission unblocked.

**Architecture:** Server-side validator on `Journal Entry.validate` reads BNPL clearing accounts (resolved via `Mode of Payment Account`), compares each credit to live GL balance, emits `frappe.msgprint` (orange indicator) when exceeded — never throws. Client-side `doctype_js` adds a button that opens a dialog (Mode of Payment + Bank Account picker), then clears the JE accounts table and inserts three pre-resolved rows.

**Tech Stack:** Frappe v15, Python 3, ERPNext 15. Tests via `bench run-tests` on rmax_dev2. Deploy via Server Manager API to RMAX server only (UAT skipped this phase).

**Spec:** `docs/superpowers/specs/2026-04-28-bnpl-settlement-teardown-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `rmax_custom/bnpl_clearing_guard.py` *(new)* | `warn_bnpl_clearing_overdraw`, `_bnpl_clearing_accounts`, `_gl_balance_excluding` |
| `rmax_custom/api/bnpl.py` *(extend)* | `get_clearing_account_for_mop`, `get_clearing_balance` whitelisted endpoints |
| `rmax_custom/public/js/journal_entry_bnpl_template.js` *(new)* | Button + dialog + accounts-table loader |
| `rmax_custom/hooks.py` *(modify)* | Wire `doctype_js` for Journal Entry; wire `validate` doc_event; drop deleted-DocType references in fixture filter |
| `rmax_custom/setup.py` *(modify)* | Drop settlement-specific bootstrap calls |
| `rmax_custom/bnpl_settlement_setup.py` *(modify)* | Strip BNPL Settlement creation paths; keep clearing + fee account creation |
| `rmax_custom/fixtures/custom_field.json` *(modify)* | Remove `Sales Invoice-custom_bnpl_settlement` and `Sales Invoice-custom_bnpl_settled` entries |
| `rmax_custom/rmax_custom/report/bnpl_surcharge_collected/bnpl_surcharge_collected.py` *(modify)* | Drop Settlement linkage; group by Mode of Payment via `custom_pos_payments_json` |
| `rmax_custom/rmax_custom/doctype/bnpl_settlement/` | **Delete** |
| `rmax_custom/rmax_custom/doctype/bnpl_settlement_invoice/` | **Delete** |
| `rmax_custom/rmax_custom/report/bnpl_pending_settlement/` | **Delete** |
| `rmax_custom/tests/__init__.py` *(new if missing)* | Test package marker |
| `rmax_custom/tests/test_bnpl_clearing_guard.py` *(new)* | Unit tests for guard helpers |
| `rmax_custom/tests/test_bnpl_api.py` *(new)* | Unit tests for whitelisted API |
| `rmax_custom/migrations/2026_04_28_drop_bnpl_settlement.py` *(new, one-shot script)* | One-shot script for `bench execute` to delete DocTypes/report/fields |

---

## Task 1: Add tests scaffold

**Files:**
- Create: `rmax_custom/tests/__init__.py`
- Create: `rmax_custom/tests/test_bnpl_clearing_guard.py` (skeleton)

- [ ] **Step 1: Create tests package**

```bash
mkdir -p /Users/sayanthns/Documents/RMAX/RMAX-Custom/rmax_custom/tests
```

Then write `rmax_custom/tests/__init__.py`:

```python
# Test package for rmax_custom.
```

- [ ] **Step 2: Create empty test module**

Write `rmax_custom/tests/test_bnpl_clearing_guard.py`:

```python
"""
Unit tests for rmax_custom.bnpl_clearing_guard.

Run via: bench --site rmax_dev2 run-tests --module rmax_custom.tests.test_bnpl_clearing_guard
"""

import frappe
import unittest


class TestBnplClearingGuard(unittest.TestCase):
    def test_placeholder(self):
        self.assertTrue(True)
```

- [ ] **Step 3: Commit**

```bash
cd /Users/sayanthns/Documents/RMAX/RMAX-Custom
git add rmax_custom/tests/__init__.py rmax_custom/tests/test_bnpl_clearing_guard.py
git commit -m "test(bnpl): scaffold tests package for clearing guard"
```

---

## Task 2: `_bnpl_clearing_accounts(company)` helper

**Files:**
- Create: `rmax_custom/bnpl_clearing_guard.py`
- Test: `rmax_custom/tests/test_bnpl_clearing_guard.py`

- [ ] **Step 1: Write the failing test**

Replace `test_placeholder` in `test_bnpl_clearing_guard.py` with:

```python
import frappe
import unittest

from rmax_custom.bnpl_clearing_guard import _bnpl_clearing_accounts


class TestBnplClearingAccounts(unittest.TestCase):
    def setUp(self):
        # Use the first non-disabled Company; rmax_dev2 has at least RMAX.
        self.company = frappe.db.get_value(
            "Company", {"is_group": 0}, "name"
        )

    def test_returns_set_of_account_names(self):
        accounts = _bnpl_clearing_accounts(self.company)
        self.assertIsInstance(accounts, set)

    def test_includes_only_mops_with_surcharge(self):
        # Tabby has surcharge > 0 on rmax_dev2; its clearing account must be
        # in the set when configured for this Company.
        tabby_clearing = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": "Tabby", "company": self.company},
            "default_account",
        )
        if not tabby_clearing:
            self.skipTest("Tabby not configured on this Company")
        accounts = _bnpl_clearing_accounts(self.company)
        self.assertIn(tabby_clearing, accounts)

    def test_empty_for_unknown_company(self):
        accounts = _bnpl_clearing_accounts("__nonexistent__")
        self.assertEqual(accounts, set())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
ssh-via-server-manager: cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.tests.test_bnpl_clearing_guard
```

Expected: `ImportError: cannot import name '_bnpl_clearing_accounts' from 'rmax_custom.bnpl_clearing_guard'`.

- [ ] **Step 3: Write minimal implementation**

Write `rmax_custom/bnpl_clearing_guard.py`:

```python
"""
Soft balance guard on Journal Entries that credit BNPL clearing accounts.

The set of "BNPL clearing accounts" is the union of `default_account` values
on `Mode of Payment Account` rows whose parent Mode of Payment carries a
positive `custom_surcharge_percentage`. The set is scoped per Company.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt


def _bnpl_clearing_accounts(company: str) -> set[str]:
    """Return the set of clearing-account names for BNPL MoPs on this Company."""
    if not company:
        return set()

    rows = frappe.db.sql(
        """
        SELECT mpa.default_account
        FROM `tabMode of Payment Account` mpa
        INNER JOIN `tabMode of Payment` mop
            ON mop.name = mpa.parent
        WHERE mpa.company = %(company)s
          AND mpa.default_account IS NOT NULL
          AND mpa.default_account != ''
          AND IFNULL(mop.custom_surcharge_percentage, 0) > 0
        """,
        {"company": company},
        as_dict=True,
    )
    return {row.default_account for row in rows}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.tests.test_bnpl_clearing_guard
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/bnpl_clearing_guard.py rmax_custom/tests/test_bnpl_clearing_guard.py
git commit -m "feat(bnpl): _bnpl_clearing_accounts(company) helper

Resolves the set of clearing accounts for BNPL Modes of Payment per
company. Backbone for the JE overdraw soft-warn validator."
```

---

## Task 3: `_gl_balance_excluding(account, voucher_no)` helper

**Files:**
- Modify: `rmax_custom/bnpl_clearing_guard.py`
- Test: `rmax_custom/tests/test_bnpl_clearing_guard.py`

- [ ] **Step 1: Write the failing test**

Append to `test_bnpl_clearing_guard.py`:

```python
from rmax_custom.bnpl_clearing_guard import _gl_balance_excluding


class TestGLBalanceExcluding(unittest.TestCase):
    def test_zero_for_account_with_no_entries(self):
        # Use a fresh test account; create + clean up
        company = frappe.db.get_value("Company", {"is_group": 0}, "name")
        abbr = frappe.db.get_value("Company", company, "abbr")
        acc_name = f"__Test BNPL Balance - {abbr}"
        if not frappe.db.exists("Account", acc_name):
            parent = frappe.db.get_value(
                "Account",
                {"company": company, "is_group": 1, "root_type": "Asset"},
                "name",
            )
            acc = frappe.get_doc({
                "doctype": "Account",
                "account_name": "__Test BNPL Balance",
                "parent_account": parent,
                "company": company,
                "account_type": "Bank",
                "is_group": 0,
            }).insert(ignore_permissions=True)
            acc_name = acc.name
        try:
            self.assertEqual(_gl_balance_excluding(acc_name, "FAKE-VOUCHER"), 0.0)
        finally:
            frappe.delete_doc("Account", acc_name, force=True)
```

- [ ] **Step 2: Run test to verify it fails**

Expected: `ImportError: cannot import name '_gl_balance_excluding'`.

- [ ] **Step 3: Implement**

Append to `bnpl_clearing_guard.py`:

```python
def _gl_balance_excluding(account: str, voucher_no: str | None) -> float:
    """Sum of (debit - credit) for an account, excluding a specific voucher.

    Uses GL Entry rather than Account.balance so we can exclude the in-flight
    Journal Entry (defensive — GL is normally posted on submit, not validate).
    """
    if not account:
        return 0.0
    rows = frappe.db.sql(
        """
        SELECT
            COALESCE(SUM(IFNULL(debit, 0) - IFNULL(credit, 0)), 0) AS bal
        FROM `tabGL Entry`
        WHERE account = %(account)s
          AND IFNULL(is_cancelled, 0) = 0
          AND (voucher_no IS NULL OR voucher_no != %(voucher_no)s)
        """,
        {"account": account, "voucher_no": voucher_no or ""},
        as_dict=True,
    )
    return flt(rows[0].bal) if rows else 0.0
```

- [ ] **Step 4: Run tests**

Expected: previous 3 tests + this 1 = 4 pass.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/bnpl_clearing_guard.py rmax_custom/tests/test_bnpl_clearing_guard.py
git commit -m "feat(bnpl): _gl_balance_excluding helper

Reads the account's running balance from tabGL Entry, excluding a
named voucher. Used so the JE validator does not read its own pending
entries."
```

---

## Task 4: `warn_bnpl_clearing_overdraw(doc, method)` validator

**Files:**
- Modify: `rmax_custom/bnpl_clearing_guard.py`
- Test: `rmax_custom/tests/test_bnpl_clearing_guard.py`

- [ ] **Step 1: Write the failing test**

Append to `test_bnpl_clearing_guard.py`:

```python
from unittest.mock import MagicMock

from rmax_custom.bnpl_clearing_guard import warn_bnpl_clearing_overdraw


class TestWarnOverdraw(unittest.TestCase):
    def setUp(self):
        self.company = frappe.db.get_value("Company", {"is_group": 0}, "name")
        self.tabby_clearing = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": "Tabby", "company": self.company},
            "default_account",
        )
        if not self.tabby_clearing:
            self.skipTest("Tabby not configured on this Company")

    def _build_doc(self, credit_amount):
        doc = MagicMock()
        doc.company = self.company
        doc.name = "__TEST_JE_DRAFT__"
        row = MagicMock()
        row.account = self.tabby_clearing
        row.account_currency = "SAR"
        row.credit_in_account_currency = credit_amount
        row.debit_in_account_currency = 0
        doc.accounts = [row]
        return doc

    def test_no_message_when_credit_below_balance(self):
        # Credit of 0 — never above balance
        frappe.message_log = []
        warn_bnpl_clearing_overdraw(self._build_doc(0))
        self.assertEqual(frappe.message_log, [])

    def test_message_when_credit_exceeds_balance(self):
        # Credit way above any plausible balance triggers the warn.
        frappe.message_log = []
        warn_bnpl_clearing_overdraw(self._build_doc(10**9))
        self.assertTrue(
            any("Clearing Balance Exceeded" in (m.get("title") or "")
                or "Clearing Balance Exceeded" in str(m)
                for m in frappe.message_log),
            f"expected warn in message_log, got: {frappe.message_log}",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Expected: `ImportError: cannot import name 'warn_bnpl_clearing_overdraw'`.

- [ ] **Step 3: Implement**

Append to `bnpl_clearing_guard.py`:

```python
from frappe import _
from frappe.utils import fmt_money

ROUNDING_TOLERANCE = 0.01


def warn_bnpl_clearing_overdraw(doc, method=None):
    """Soft warn (no throw) when a JE credits more than the live BNPL clearing balance."""
    if doc.doctype != "Journal Entry":
        return
    company = getattr(doc, "company", None)
    if not company:
        return
    clearing_accounts = _bnpl_clearing_accounts(company)
    if not clearing_accounts:
        return
    seen = {}
    for row in (doc.get("accounts") or []):
        if row.account not in clearing_accounts:
            continue
        credit = flt(row.credit_in_account_currency)
        if credit <= 0:
            continue
        seen[row.account] = seen.get(row.account, 0.0) + credit
    if not seen:
        return
    for account, credit in seen.items():
        live_balance = _gl_balance_excluding(account, doc.name)
        if credit > live_balance + ROUNDING_TOLERANCE:
            ccy = frappe.db.get_value("Account", account, "account_currency") or ""
            frappe.msgprint(
                _(
                    "Credit to {0} ({1}) exceeds current balance ({2}). "
                    "Continuing — verify with the BNPL provider statement."
                ).format(
                    account,
                    fmt_money(credit, currency=ccy),
                    fmt_money(live_balance, currency=ccy),
                ),
                title=_("BNPL Clearing Balance Exceeded"),
                indicator="orange",
            )
```

- [ ] **Step 4: Run tests**

```bash
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.tests.test_bnpl_clearing_guard
```

Expected: 6 tests pass (or 5 if Tabby not configured; the Tabby-dependent tests skip).

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/bnpl_clearing_guard.py rmax_custom/tests/test_bnpl_clearing_guard.py
git commit -m "feat(bnpl): warn_bnpl_clearing_overdraw validator

Soft warn (orange indicator, never throws) when a JE credits more than
the live GL balance of a BNPL clearing account. Uses _bnpl_clearing_accounts
to scope the check per Company."
```

---

## Task 5: Wire validator to Journal Entry `validate` hook

**Files:**
- Modify: `rmax_custom/hooks.py`

- [ ] **Step 1: Edit `hooks.py` `doc_events`**

Find the `doc_events = { ... }` block. Add a `Journal Entry` key:

```python
doc_events = {
    # ... existing entries unchanged ...
    "Journal Entry": {
        "validate": "rmax_custom.bnpl_clearing_guard.warn_bnpl_clearing_overdraw",
    },
}
```

If `Journal Entry` already exists in `doc_events`, append the validate handler to the existing list (convert to list if string).

- [ ] **Step 2: Smoke test by running migrate + creating a draft JE**

Deploy locally first via `git push` then dev pull (see Task 14 deploy step), then:

```bash
sudo -u v15 bench --site rmax_dev2 execute frappe.client.insert --kwargs '{"doc":{"doctype":"Journal Entry","posting_date":"2026-04-28","company":"RMAX","voucher_type":"Journal Entry","accounts":[{"account":"<tabby_clearing>","credit_in_account_currency":99999999,"debit_in_account_currency":0},{"account":"Cash - R","credit_in_account_currency":0,"debit_in_account_currency":99999999}]}}'
```

Expected: insert succeeds; `frappe.message_log` contains the orange warn.

- [ ] **Step 3: Commit**

```bash
git add rmax_custom/hooks.py
git commit -m "feat(bnpl): wire warn_bnpl_clearing_overdraw to Journal Entry validate"
```

---

## Task 6: Whitelisted API endpoints

**Files:**
- Modify: `rmax_custom/api/bnpl.py`
- Create: `rmax_custom/tests/test_bnpl_api.py`

- [ ] **Step 1: Write the failing test**

Write `rmax_custom/tests/test_bnpl_api.py`:

```python
import frappe
import unittest

from rmax_custom.api.bnpl import (
    get_clearing_account_for_mop,
    get_clearing_balance,
)


class TestBnplApi(unittest.TestCase):
    def setUp(self):
        self.company = frappe.db.get_value("Company", {"is_group": 0}, "name")

    def test_clearing_account_for_known_mop(self):
        if not frappe.db.exists("Mode of Payment", "Tabby"):
            self.skipTest("Tabby MoP not present")
        result = get_clearing_account_for_mop(mop="Tabby", company=self.company)
        self.assertIsInstance(result, dict)
        self.assertIn("account", result)

    def test_clearing_account_missing_returns_none_account(self):
        result = get_clearing_account_for_mop(mop="__nonexistent__", company=self.company)
        self.assertIsNone(result.get("account"))

    def test_clearing_balance_zero_for_unknown_account(self):
        bal = get_clearing_balance(account="__nope__")
        self.assertEqual(bal, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Expected: `ImportError`.

- [ ] **Step 3: Append to `rmax_custom/api/bnpl.py`**

```python
import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_clearing_account_for_mop(mop: str, company: str) -> dict:
    """Resolve clearing account + currency for a (Mode of Payment, Company) pair.

    Returns: {"account": <account name or None>, "currency": <ccy or None>}.
    """
    if not (mop and company):
        return {"account": None, "currency": None}
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mop, "company": company},
        "default_account",
    )
    currency = (
        frappe.db.get_value("Account", account, "account_currency") if account else None
    )
    return {"account": account, "currency": currency}


@frappe.whitelist()
def get_clearing_balance(account: str) -> float:
    """Live balance of an account (debit - credit across all GL entries)."""
    if not account or not frappe.db.exists("Account", account):
        return 0.0
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(IFNULL(debit, 0) - IFNULL(credit, 0)), 0) AS bal
        FROM `tabGL Entry`
        WHERE account = %(account)s AND IFNULL(is_cancelled, 0) = 0
        """,
        {"account": account},
        as_dict=True,
    )
    return flt(rows[0].bal) if rows else 0.0
```

- [ ] **Step 4: Run tests**

```bash
sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.tests.test_bnpl_api
```

Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/api/bnpl.py rmax_custom/tests/test_bnpl_api.py
git commit -m "feat(bnpl): whitelisted endpoints for clearing account + balance

Used by the JE template loader on the client to resolve heads and show
live balance."
```

---

## Task 7: JE template loader — JS button + dialog

**Files:**
- Create: `rmax_custom/public/js/journal_entry_bnpl_template.js`
- Modify: `rmax_custom/hooks.py`

- [ ] **Step 1: Create the JS file**

Write `rmax_custom/public/js/journal_entry_bnpl_template.js`:

```javascript
// rmax_custom: Load BNPL Settlement template into Journal Entry accounts table.
frappe.ui.form.on("Journal Entry", {
    refresh: function (frm) {
        if (frm._rmax_bnpl_btn) return;
        if (frm.doc.docstatus !== 0) return;
        if (!["Journal Entry", "Bank Entry"].includes(frm.doc.voucher_type)) return;

        const allowed = ["Accounts User", "Accounts Manager", "System Manager"];
        if (!frappe.user_roles.some((r) => allowed.includes(r))) return;

        frm.add_custom_button(__("Load BNPL Settlement"), function () {
            rmax_show_bnpl_settlement_dialog(frm);
        });
        frm._rmax_bnpl_btn = true;
    },
});

function rmax_show_bnpl_settlement_dialog(frm) {
    if (!frm.doc.company) {
        frappe.msgprint(__("Pick a Company first."));
        return;
    }

    const d = new frappe.ui.Dialog({
        title: __("Load BNPL Settlement"),
        fields: [
            {
                fieldname: "mop",
                fieldtype: "Link",
                label: __("Mode of Payment"),
                options: "Mode of Payment",
                reqd: 1,
                get_query: function () {
                    return {
                        filters: { custom_surcharge_percentage: [">", 0] },
                    };
                },
                onchange: function () {
                    rmax_refresh_clearing_info(d, frm);
                },
            },
            {
                fieldname: "bank_account",
                fieldtype: "Link",
                label: __("Bank Account"),
                options: "Account",
                reqd: 1,
                get_query: function () {
                    return {
                        filters: {
                            company: frm.doc.company,
                            is_group: 0,
                            account_type: ["in", ["Bank", "Cash"]],
                        },
                    };
                },
            },
            { fieldtype: "Section Break" },
            {
                fieldname: "clearing_info",
                fieldtype: "HTML",
                label: __("Clearing Account Info"),
            },
        ],
        primary_action_label: __("Load Heads"),
        primary_action: function (vals) {
            rmax_load_bnpl_heads(frm, d, vals);
        },
    });
    d.show();
}

function rmax_refresh_clearing_info(d, frm) {
    const mop = d.get_value("mop");
    const $info = d.fields_dict.clearing_info.$wrapper;
    if (!mop) {
        $info.html("");
        return;
    }
    frappe.call({
        method: "rmax_custom.api.bnpl.get_clearing_account_for_mop",
        args: { mop: mop, company: frm.doc.company },
        callback: function (r) {
            const res = r.message || {};
            if (!res.account) {
                $info.html(
                    `<div style="color:#b54708;">${__(
                        "No clearing account configured for {0} on {1}. Configure Mode of Payment Account first.",
                        [mop, frm.doc.company]
                    )}</div>`
                );
                return;
            }
            frappe.call({
                method: "rmax_custom.api.bnpl.get_clearing_balance",
                args: { account: res.account },
                callback: function (r2) {
                    const bal = (r2.message || 0).toFixed(2);
                    $info.html(
                        `<div><strong>${__("Clearing Account")}:</strong> ${res.account}<br>
                         <strong>${__("Currency")}:</strong> ${res.currency || ""}<br>
                         <strong>${__("Live Balance")}:</strong> ${bal}</div>`
                    );
                },
            });
        },
    });
}

function rmax_load_bnpl_heads(frm, d, vals) {
    frappe.call({
        method: "rmax_custom.api.bnpl.get_clearing_account_for_mop",
        args: { mop: vals.mop, company: frm.doc.company },
        callback: function (r) {
            const res = r.message || {};
            if (!res.account) {
                frappe.msgprint({
                    title: __("Setup Missing"),
                    message: __(
                        "Configure a default account for {0} on Company {1} (Mode of Payment Account table).",
                        [vals.mop, frm.doc.company]
                    ),
                    indicator: "red",
                });
                return;
            }
            const fee_account = frappe.db.get_value(
                "Company",
                frm.doc.company,
                "abbr"
            );
            // Resolve fee account name client-side via convention; if missing, fall
            // back to a server lookup for any account named like 'BNPL Fee Expense%'.
            frappe.db
                .get_value("Account", {
                    company: frm.doc.company,
                    account_name: ["like", "BNPL Fee Expense%"],
                    is_group: 0,
                }, "name")
                .then(function (rr) {
                    const fee = (rr.message || {}).name;
                    if (!fee) {
                        frappe.msgprint({
                            title: __("Setup Missing"),
                            message: __(
                                "No 'BNPL Fee Expense' account on Company {0}. Re-run setup_bnpl_accounts.",
                                [frm.doc.company]
                            ),
                            indicator: "red",
                        });
                        return;
                    }
                    frappe.confirm(
                        __("This replaces the existing accounts table. Continue?"),
                        function () {
                            frm.clear_table("accounts");
                            const r1 = frm.add_child("accounts");
                            r1.account = vals.bank_account;
                            r1.debit_in_account_currency = 0;
                            r1.credit_in_account_currency = 0;
                            const r2 = frm.add_child("accounts");
                            r2.account = fee;
                            r2.debit_in_account_currency = 0;
                            r2.credit_in_account_currency = 0;
                            const r3 = frm.add_child("accounts");
                            r3.account = res.account;
                            r3.debit_in_account_currency = 0;
                            r3.credit_in_account_currency = 0;
                            frm.refresh_field("accounts");
                            if (!frm.doc.user_remark) {
                                frm.set_value(
                                    "user_remark",
                                    __("BNPL Settlement — {0}", [vals.mop])
                                );
                            }
                            d.hide();
                        }
                    );
                });
        },
    });
}
```

- [ ] **Step 2: Wire `doctype_js` in hooks.py**

Find `doctype_js = { ... }`. Add:

```python
doctype_js = {
    # ... existing ...
    "Journal Entry": "public/js/journal_entry_bnpl_template.js",
}
```

If `Journal Entry` exists already, append the path to a list.

- [ ] **Step 3: Smoke test in browser**

After deploy (Task 14): open a draft Journal Entry, click "Load BNPL Settlement", pick Tabby + a bank account, confirm — three rows appear.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/public/js/journal_entry_bnpl_template.js rmax_custom/hooks.py
git commit -m "feat(bnpl): JE button to load Tabby/Tamara settlement heads

Adds a 'Load BNPL Settlement' button on draft Journal Entries (visible
to Accounts User/Manager). Dialog picks Mode of Payment + Bank Account
and inserts three rows (Bank, Fee Expense, Clearing). Live clearing
balance shown in the dialog for context."
```

---

## Task 8: Refactor `bnpl_surcharge_collected` report

**Files:**
- Modify: `rmax_custom/rmax_custom/report/bnpl_surcharge_collected/bnpl_surcharge_collected.py`
- Modify: `rmax_custom/rmax_custom/report/bnpl_surcharge_collected/bnpl_surcharge_collected.js`

- [ ] **Step 1: Read current report**

```bash
cat rmax_custom/rmax_custom/report/bnpl_surcharge_collected/bnpl_surcharge_collected.py
```

- [ ] **Step 2: Rewrite columns + query**

Replace report SQL/Python so the data source is `tabSales Invoice` with `custom_bnpl_total_uplift > 0`. Drop any join to `tabBNPL Settlement`. Group by Mode of Payment by parsing `custom_pos_payments_json` per row, attributing uplift proportionally (`amount_for_mop / total_payment * custom_bnpl_total_uplift`).

```python
import json
import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = _columns()
    rows = _rows(filters)
    return columns, rows


def _columns():
    return [
        {"label": "Sales Invoice", "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": "Mode of Payment", "fieldname": "mode_of_payment", "fieldtype": "Link", "options": "Mode of Payment", "width": 140},
        {"label": "BNPL Uplift Attributed", "fieldname": "uplift", "fieldtype": "Currency", "width": 160},
        {"label": "Original Items Total", "fieldname": "original_total", "fieldtype": "Currency", "width": 160},
    ]


def _rows(filters):
    conds = ["si.docstatus = 1", "IFNULL(si.custom_bnpl_total_uplift, 0) > 0"]
    args = {}
    if filters.get("company"):
        conds.append("si.company = %(company)s"); args["company"] = filters["company"]
    if filters.get("from_date"):
        conds.append("si.posting_date >= %(from_date)s"); args["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conds.append("si.posting_date <= %(to_date)s"); args["to_date"] = filters["to_date"]
    sql = f"""
        SELECT si.name AS sales_invoice, si.posting_date, si.customer,
               si.custom_bnpl_total_uplift, si.custom_pos_payments_json,
               (SELECT COALESCE(SUM(sii.qty * sii.custom_original_rate), 0)
                FROM `tabSales Invoice Item` sii
                WHERE sii.parent = si.name) AS original_total
        FROM `tabSales Invoice` si
        WHERE {' AND '.join(conds)}
        ORDER BY si.posting_date DESC
    """
    raw = frappe.db.sql(sql, args, as_dict=True)
    out = []
    mop_filter = filters.get("mode_of_payment")
    for r in raw:
        attrib = _attribute_uplift(r)
        for mop, share in attrib.items():
            if mop_filter and mop != mop_filter:
                continue
            out.append({
                "sales_invoice": r.sales_invoice,
                "posting_date": r.posting_date,
                "customer": r.customer,
                "mode_of_payment": mop,
                "uplift": flt(share),
                "original_total": flt(r.original_total),
            })
    return out


def _attribute_uplift(row):
    """Distribute custom_bnpl_total_uplift across BNPL Modes of Payment based on snapshot."""
    raw = row.get("custom_pos_payments_json")
    total_uplift = flt(row.get("custom_bnpl_total_uplift"))
    if not raw or total_uplift <= 0:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = []
    bnpl_modes = {}
    bnpl_total = 0.0
    for p in parsed:
        if not isinstance(p, dict):
            continue
        mop = p.get("mode_of_payment")
        amt = flt(p.get("amount"))
        if not mop or amt <= 0:
            continue
        pct = flt(frappe.db.get_value("Mode of Payment", mop, "custom_surcharge_percentage"))
        if pct > 0:
            bnpl_modes[mop] = bnpl_modes.get(mop, 0.0) + amt
            bnpl_total += amt
    if bnpl_total <= 0:
        return {}
    return {mop: total_uplift * (amt / bnpl_total) for mop, amt in bnpl_modes.items()}
```

- [ ] **Step 3: Update the report JS filters**

Edit `bnpl_surcharge_collected.js` to expose: Company (Link), From Date, To Date, Mode of Payment (Link). Drop any "Settlement" filter.

```javascript
frappe.query_reports["BNPL Surcharge Collected"] = {
    filters: [
        { fieldname: "company", label: "Company", fieldtype: "Link", options: "Company", reqd: 1, default: frappe.defaults.get_user_default("Company") },
        { fieldname: "from_date", label: "From Date", fieldtype: "Date", default: frappe.datetime.month_start() },
        { fieldname: "to_date", label: "To Date", fieldtype: "Date", default: frappe.datetime.month_end() },
        { fieldname: "mode_of_payment", label: "Mode of Payment", fieldtype: "Link", options: "Mode of Payment" },
    ],
};
```

- [ ] **Step 4: Smoke test post-deploy**

```bash
sudo -u v15 bench --site rmax_dev2 execute "rmax_custom.rmax_custom.report.bnpl_surcharge_collected.bnpl_surcharge_collected.execute" --kwargs '{"filters":{"company":"RMAX"}}'
```

Expected: returns columns + rows; numbers match a known invoice's uplift.

- [ ] **Step 5: Commit**

```bash
git add rmax_custom/rmax_custom/report/bnpl_surcharge_collected/
git commit -m "refactor(bnpl): drop BNPL Settlement linkage from surcharge report

Source uplift attribution from Sales Invoice + custom_pos_payments_json
instead of the Settlement DocType. Filter by Mode of Payment instead of
Settlement reference."
```

---

## Task 9: Remove SI custom fields tied to BNPL Settlement

**Files:**
- Modify: `rmax_custom/fixtures/custom_field.json`
- Modify: `rmax_custom/hooks.py` (fixtures filter list)

- [ ] **Step 1: Locate field entries**

```bash
grep -n "custom_bnpl_settlement\|custom_bnpl_settled" rmax_custom/fixtures/custom_field.json
```

- [ ] **Step 2: Delete the JSON entries**

Open `custom_field.json`, remove the entire object for each of:
- `Sales Invoice-custom_bnpl_settlement`
- `Sales Invoice-custom_bnpl_settled`
- Any section / column break inserted exclusively between them (check `insert_after` references and rotate them so the chain stays intact).

Re-grep to confirm zero references remain.

- [ ] **Step 3: Update `hooks.py` fixture filter**

Find lines like:

```python
{"fieldname": "name", "operator": "in", "value": [..., "Sales Invoice-custom_bnpl_settlement", ...]}
```

Remove the two field names from the value list.

- [ ] **Step 4: Commit (no migration yet — that runs in Task 11)**

```bash
git add rmax_custom/fixtures/custom_field.json rmax_custom/hooks.py
git commit -m "refactor(bnpl): drop SI custom fields for Settlement linkage

Removes custom_bnpl_settlement (Link) and custom_bnpl_settled (Check)
plus their layout breaks. Field deletion runs as a one-shot migration
(see migrations/2026_04_28_drop_bnpl_settlement.py)."
```

---

## Task 10: Strip Settlement-creation paths from `bnpl_settlement_setup.py`

**Files:**
- Modify: `rmax_custom/bnpl_settlement_setup.py`
- Modify: `rmax_custom/setup.py`

- [ ] **Step 1: Read current file**

```bash
cat rmax_custom/bnpl_settlement_setup.py
```

- [ ] **Step 2: Keep only account-creation logic**

Remove any function or block that:
- Inserts a default BNPL Settlement record
- Creates Property Setters / DocPerms tied to BNPL Settlement
- References `BNPL Settlement` or `BNPL Settlement Invoice` doctype names

Keep:
- Clearing account creation per BNPL MoP per Company
- BNPL Fee Expense account creation per Company
- Mode of Payment Account row insertion

- [ ] **Step 3: Verify `setup.py` still calls `setup_bnpl_accounts`**

```bash
grep -n "setup_bnpl_accounts\|bnpl_settlement_setup" rmax_custom/setup.py
```

If any leftover call references a removed function, drop the call.

- [ ] **Step 4: Commit**

```bash
git add rmax_custom/bnpl_settlement_setup.py rmax_custom/setup.py
git commit -m "refactor(bnpl): strip Settlement DocType creation from setup

Account-head creation (clearing + fee + MoP-Account rows) stays. All
BNPL Settlement inserts and Property Setter scaffolding removed."
```

---

## Task 11: One-shot migration script

**Files:**
- Create: `rmax_custom/migrations/__init__.py` (if absent)
- Create: `rmax_custom/migrations/drop_bnpl_settlement.py`

- [ ] **Step 1: Create migrations package**

```bash
mkdir -p rmax_custom/migrations
touch rmax_custom/migrations/__init__.py
```

- [ ] **Step 2: Write the script**

`rmax_custom/migrations/drop_bnpl_settlement.py`:

```python
"""
One-shot migration: drop BNPL Settlement DocTypes, BNPL Pending Settlement
report, and the two SI custom fields that linked invoices to Settlements.

Run with:
    bench --site rmax_dev2 execute rmax_custom.migrations.drop_bnpl_settlement.run
"""

from __future__ import annotations

import frappe


DOCTYPES_TO_DROP = ["BNPL Settlement Invoice", "BNPL Settlement"]
REPORT_TO_DROP = "BNPL Pending Settlement"
CUSTOM_FIELDS_TO_DROP = [
    "Sales Invoice-custom_bnpl_settlement",
    "Sales Invoice-custom_bnpl_settled",
]


def run():
    _drop_custom_fields()
    _drop_report()
    _drop_doctypes()
    frappe.db.commit()


def _drop_custom_fields():
    for name in CUSTOM_FIELDS_TO_DROP:
        if frappe.db.exists("Custom Field", name):
            frappe.delete_doc("Custom Field", name, force=True)
            print(f"  - dropped Custom Field: {name}")


def _drop_report():
    if frappe.db.exists("Report", REPORT_TO_DROP):
        frappe.delete_doc("Report", REPORT_TO_DROP, force=True)
        print(f"  - dropped Report: {REPORT_TO_DROP}")


def _drop_doctypes():
    for dt in DOCTYPES_TO_DROP:
        # Delete records first if any (force).
        if frappe.db.exists("DocType", dt):
            count = frappe.db.count(dt)
            if count:
                frappe.db.sql(f"DELETE FROM `tab{dt}`")
                print(f"  - cleared {count} rows from tab{dt}")
            frappe.delete_doc("DocType", dt, force=True, ignore_missing=True)
            print(f"  - dropped DocType: {dt}")
```

- [ ] **Step 3: Commit**

```bash
git add rmax_custom/migrations/__init__.py rmax_custom/migrations/drop_bnpl_settlement.py
git commit -m "feat(bnpl): one-shot migration to drop Settlement scaffolding

Removes the two DocTypes, the Pending Settlement report, and the two SI
custom fields. Run via:
  bench --site rmax_dev2 execute rmax_custom.migrations.drop_bnpl_settlement.run"
```

---

## Task 12: Delete DocType + report folders from disk

**Files:**
- Delete: `rmax_custom/rmax_custom/doctype/bnpl_settlement/`
- Delete: `rmax_custom/rmax_custom/doctype/bnpl_settlement_invoice/`
- Delete: `rmax_custom/rmax_custom/report/bnpl_pending_settlement/`

- [ ] **Step 1: Confirm nothing imports these modules**

```bash
grep -rn "bnpl_settlement\|bnpl_pending_settlement" rmax_custom/ \
    --include="*.py" --include="*.js" --include="*.json" \
    | grep -v "rmax_custom/rmax_custom/doctype/bnpl_settlement" \
    | grep -v "rmax_custom/rmax_custom/doctype/bnpl_settlement_invoice" \
    | grep -v "rmax_custom/rmax_custom/report/bnpl_pending_settlement" \
    | grep -v "rmax_custom/migrations/drop_bnpl_settlement.py"
```

Expected: no output. If any remains, fix in this task before deleting.

- [ ] **Step 2: Remove folders**

```bash
git rm -r rmax_custom/rmax_custom/doctype/bnpl_settlement
git rm -r rmax_custom/rmax_custom/doctype/bnpl_settlement_invoice
git rm -r rmax_custom/rmax_custom/report/bnpl_pending_settlement
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(bnpl): delete BNPL Settlement DocTypes + Pending Settlement report

Code paths that referenced these were removed in earlier commits in this
series. The DB rows and metadata are cleared via the one-shot migration."
```

---

## Task 13: Push + run migration on dev

**Files:** none (deploy step)

- [ ] **Step 1: Push branch**

```bash
cd /Users/sayanthns/Documents/RMAX/RMAX-Custom
git push origin main
```

- [ ] **Step 2: Pull on RMAX dev server**

```bash
curl -s -X POST -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command":"cd /home/v15/frappe-bench/apps/rmax_custom && sudo -u v15 git pull upstream main"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command
```

- [ ] **Step 3: Run migrate (custom fields removed via fixtures filter — won't re-create dropped ones)**

```bash
curl -s -X POST -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command":"cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 migrate"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command
```

- [ ] **Step 4: Run the one-shot migration**

```bash
curl -s -X POST -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command":"cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 execute rmax_custom.migrations.drop_bnpl_settlement.run"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command
```

Expected stdout includes lines like:
```
  - dropped Custom Field: Sales Invoice-custom_bnpl_settlement
  - dropped Custom Field: Sales Invoice-custom_bnpl_settled
  - dropped Report: BNPL Pending Settlement
  - dropped DocType: BNPL Settlement Invoice
  - dropped DocType: BNPL Settlement
```

- [ ] **Step 5: Clear cache + restart workers**

```bash
curl -s -X POST -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command":"cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 clear-cache && sudo supervisorctl signal QUIT frappe-bench-web:frappe-bench-frappe-web"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command
```

- [ ] **Step 6: No commit** — deploy step only.

---

## Task 14: Smoke test on dev

**Files:** none.

- [ ] **Step 1: Run unit tests on dev**

```bash
curl -s -X POST -H "Authorization: Bearer 9c9d7e54d54c30e9f264f202376c04ed4dd4bab9c57eb2b3" \
  -H "Content-Type: application/json" \
  -d '{"command":"cd /home/v15/frappe-bench && sudo -u v15 bench --site rmax_dev2 run-tests --module rmax_custom.tests.test_bnpl_clearing_guard --module rmax_custom.tests.test_bnpl_api"}' \
  http://207.180.209.80:3847/api/servers/41ef79dc-a2fd-418a-bd88-b5f5173aeaf7/command
```

Expected: all tests pass / skip cleanly.

- [ ] **Step 2: Manual UI test — JE template button**

1. Browser: `https://rmax-dev.fateherp.com/app/journal-entry/new?voucher_type=Bank+Entry`
2. Pick Company `RMAX`.
3. Hard reload to bust JS cache.
4. Confirm "Load BNPL Settlement" button visible.
5. Click → dialog opens → pick `Tabby` → balance shown.
6. Pick a Bank Account → click "Load Heads" → confirm three rows inserted.
7. Type credit amount on the Clearing row that exceeds balance → orange warn appears on save.
8. Save (not submit) — verify warn was non-blocking.

- [ ] **Step 3: Verify drops**

1. `https://rmax-dev.fateherp.com/app/bnpl-settlement` — should 404.
2. `https://rmax-dev.fateherp.com/app/query-report/BNPL+Pending+Settlement` — should 404.
3. Sales Invoice form — `custom_bnpl_settlement` and `custom_bnpl_settled` fields not visible.

- [ ] **Step 4: Verify the surcharge collected report**

`https://rmax-dev.fateherp.com/app/query-report/BNPL+Surcharge+Collected` — runs without referencing Settlement, returns rows for invoices with uplift.

---

## Self-Review

**Spec coverage:**
- §4 Removals → Task 9 (custom fields), Task 10 (setup paths), Task 11 (migration), Task 12 (folder deletes). Covered.
- §5 Keep → no work needed; tasks above don't touch the keep list. Covered.
- §6 New JE template loader → Task 7. Covered.
- §7 Soft warn validator → Tasks 2/3/4/5. Covered.
- §8 Surcharge collected refactor → Task 8. Covered.
- §9 Edge cases → handled across Tasks 4, 7, 11.
- §10 Migration steps → Tasks 11, 13. Covered.
- §11 Roles → Task 7 enforces role check in JS.
- §13 Test plan → Tasks 2/3/4/6/14. Covered.

**Placeholder scan:** none of the red-flag patterns appear; every code step has actual code.

**Type consistency:** `_bnpl_clearing_accounts(company)` returns `set[str]` everywhere. `_gl_balance_excluding(account, voucher_no)` returns `float`. `get_clearing_account_for_mop` returns `dict` with keys `account` + `currency` (matches JS callsites). `get_clearing_balance` returns `float` (matches JS). `warn_bnpl_clearing_overdraw(doc, method=None)` matches Frappe doc_event signature.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-28-bnpl-settlement-teardown.md`.

Two execution options:
1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, faster iteration.
2. **Inline Execution** — run tasks here in this session with checkpoints for review.

Which?
