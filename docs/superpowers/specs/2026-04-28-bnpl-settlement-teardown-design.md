# BNPL Settlement Teardown + Journal Entry Template

**Date:** 2026-04-28
**Status:** Draft (pending client review)
**Scope:** rmax_dev2 only — no UAT rollout in this phase

---

## 1. Problem

Current BNPL Settlement custom DocType duplicates what a plain Journal Entry already does. Operators must learn an extra DocType, and the workflow is rigid (one settlement per provider per submission). The finance team prefers a single Journal Entry per payout with the right account heads pre-loaded.

## 2. Goals

- Drop the BNPL Settlement DocType and its surrounding scaffolding.
- Provide a one-click Journal Entry template loader for Tabby / Tamara payouts.
- Soft-warn (not block) if the credit amount to a BNPL clearing account exceeds the live GL balance — finance should be able to override for legitimate edge cases (refunds, write-offs, manual carry-forward).
- Preserve everything that the BNPL surcharge mechanism depends on — clearing accounts, fee accounts, surcharge percentage, uplift logic, surcharge popup, and the `bnpl_surcharge_collected` report.

## 3. Non-goals

- No data migration. No submitted BNPL Settlement records exist on rmax_dev2.
- No UAT deploy in this phase — clean dev cut, observe a few real settlements, then cut over.
- No new reporting in this phase — `bnpl_surcharge_collected` is refactored, no new report added.

## 4. Removals

| Artifact | Path |
|---|---|
| DocType | `rmax_custom/rmax_custom/doctype/bnpl_settlement/` |
| Child DocType | `rmax_custom/rmax_custom/doctype/bnpl_settlement_invoice/` |
| Report | `rmax_custom/rmax_custom/report/bnpl_pending_settlement/` |
| SI Custom Field | `Sales Invoice-custom_bnpl_settlement` (Link → BNPL Settlement) |
| SI Custom Field | `Sales Invoice-custom_bnpl_settled` (Check) |
| SI Custom Field | any section/column break inserted exclusively for the two fields above |
| Setup helper | `setup_bnpl_accounts` becomes account-only (drop settlement-specific bits) |

`bnpl_settlement_setup.py` keeps the parts that create:
- One clearing account per BNPL Mode of Payment per Company (Asset, Bank-type)
- One BNPL Fee Expense account per Company (Indirect Expense)
- The `Mode of Payment Account` row linking each MoP to its clearing account per Company

The function is renamed to `setup_bnpl_accounts` (already that name) and any code path that previously created or referenced BNPL Settlement is deleted.

## 5. Keep

- `Mode of Payment.custom_surcharge_percentage` (Float)
- `Sales Invoice Item.custom_original_rate`, `custom_bnpl_uplift_amount`
- `Sales Invoice.custom_bnpl_portion_ratio`, `custom_bnpl_total_uplift`, `custom_pos_payments_json`
- Hooks: `bnpl_uplift.apply_bnpl_uplift` (before_validate), `bnpl_uplift.validate_bnpl_uplift` (validate)
- Whitelisted API: `rmax_custom.api.bnpl.set_pos_payments_snapshot`
- POS payment popup (`sales_invoice_pos_total_popup.v3.js`)
- `bnpl_surcharge_collected` report — refactored to remove BNPL Settlement linkage (see §8)

## 6. New: Journal Entry Template Loader

### 6.1 Trigger

`doctype_js` on Journal Entry. Button label: **Load BNPL Settlement**.

Visibility:
- `frm.doc.docstatus === 0`
- `frm.doc.voucher_type` in `['Journal Entry', 'Bank Entry']`
- User has `Accounts User` or `Accounts Manager` or `System Manager` role
- At least one Mode of Payment with `custom_surcharge_percentage > 0` exists

If none of those hold, the button is not added.

### 6.2 Dialog

| Field | Type | Required | Notes |
|---|---|---|---|
| Mode of Payment | Link → Mode of Payment | Yes | Filtered server-side to MoPs with surcharge % > 0 |
| Bank Account | Link → Account | Yes | `account_type in ('Bank', 'Cash')`, `is_group = 0`, `company = frm.doc.company`. Always blank — user picks each time (HO-wise routing). |
| Clearing Account Balance | Read-only HTML | — | Live balance of the clearing account for the chosen MoP, refreshed when MoP changes |

Clearing account is resolved server-side from `Mode of Payment Account` for the `(Mode of Payment, Company)` pair. If missing, dialog shows an error and aborts: `"Configure a default account for {mop} on Company {company} (Mode of Payment Account table)."`

### 6.3 Action — Load

On confirm, clear the JE accounts table and append three rows in this order:

| Row | Account | Debit | Credit |
|---|---|---|---|
| 1 | Bank Account (chosen) | 0 (user fills) | 0 |
| 2 | BNPL Fee Expense - {abbr} | 0 (user fills) | 0 |
| 3 | Clearing Account (resolved) | 0 | 0 (user fills, or auto-set to row1 + row2) |

Set `frm.doc.user_remark = "BNPL Settlement — {mop}"` if remark is empty. Refresh accounts table.

User then types the bank credit amount and the fee. Standard ERPNext JE recalculation totals debits / credits. The clearing-account credit can be left to the user, or we can wire a simple JS sum (row1.debit + row2.debit → row3.credit) — TBD during implementation, but default is **leave to user** because real-world cases sometimes split across multiple clearing rows.

### 6.4 Multi-currency caveat

Bank Account currency ≠ Clearing Account currency. ERPNext handles this through `exchange_rate` on each JE row. The template loader does not set exchange rates — operator handles. If currencies differ, dialog shows a warning hint: `"Bank ({bank_ccy}) and Clearing ({clearing_ccy}) differ — set exchange rate on the bank row."`

## 7. Soft Balance Warning

`doc_events` on Journal Entry, `validate`:

```python
def warn_bnpl_clearing_overdraw(doc, method=None):
    clearing_accounts = _bnpl_clearing_accounts(doc.company)
    if not clearing_accounts:
        return
    for row in doc.accounts:
        if row.account not in clearing_accounts:
            continue
        credit = flt(row.credit_in_account_currency)
        if credit <= 0:
            continue
        live_balance = _gl_balance_excluding(row.account, doc.name)
        if credit > live_balance + ROUNDING_TOLERANCE:
            frappe.msgprint(
                _("Credit to {0} ({1}) exceeds current balance ({2}). "
                  "Continuing — verify with the BNPL provider statement.").format(
                    row.account,
                    fmt_money(credit, currency=row.account_currency),
                    fmt_money(live_balance, currency=row.account_currency),
                ),
                title=_("BNPL Clearing Balance Exceeded"),
                indicator="orange",
            )
```

Notes:
- `_bnpl_clearing_accounts(company)` reads `Mode of Payment Account` rows for the company filtered to MoPs with surcharge > 0, returns the set of `default_account` values. Cached per request.
- `_gl_balance_excluding(account, voucher_no)` sums `tabGL Entry` for `account` where `voucher_no != doc.name AND is_cancelled = 0`. This exists so that `validate` running mid-save doesn't read its own pending entries (in practice GL is posted on submit, not validate, but the exclusion is defensive).
- `ROUNDING_TOLERANCE = 0.01`.
- Message indicator is `orange` — non-blocking. `submit` proceeds.

## 8. `bnpl_surcharge_collected` report refactor

Currently filters / groups using `Sales Invoice.custom_bnpl_settlement`. Replace:
- Drop the Settlement column / filter.
- Group by Mode of Payment + posting date (existing custom field `custom_pos_payments_json` parsed, or by reading `tabSales Invoice Payment` from is_pos invoices, or by joining the Payment Entries created by the POS popup).
- Filter set: Company, From Date, To Date, Mode of Payment.
- Output columns: Sales Invoice, Posting Date, Customer, Mode of Payment, BNPL Uplift Amount, Original Rate Total.

Implementation detail: the simplest source is `Sales Invoice` rows where `custom_bnpl_total_uplift > 0`, broken down by the JSON in `custom_pos_payments_json` to attribute uplift per MoP. If JSON is empty (older invoices), fall back to `tabSales Invoice Payment`.

## 9. Edge cases

| Case | Handling |
|---|---|
| MoP missing `Mode of Payment Account` for the JE's Company | Dialog throws on confirm with a clear setup message — no rows loaded |
| Bank Account currency ≠ Clearing Account currency | Dialog shows warning hint; loader still runs; user manages `exchange_rate` per row |
| Operator deletes a row after load | No special handling — standard JE rules apply |
| Operator runs loader twice on the same draft | Existing rows cleared and reloaded (the loader is destructive — confirmed via dialog "This will replace existing rows. Continue?") |
| MoP with surcharge configured but never used | Still listed; loader works; clearing balance shows 0 |
| Clearing account balance is **negative** (overpaid in past) | Warn rule is `credit > balance`, so a negative balance with any credit triggers the warn. Acceptable — finance reviews. |
| JE submitted, then cancelled, then re-submitted | Standard ERPNext flow; warn re-evaluates against live balance each validate call |
| Old draft JEs created via the deleted BNPL Settlement → JE bridge | None expected; dev had no submitted Settlements. Any orphan draft is deleted manually before the migration. |
| Customer credit-note path that previously cleared `custom_bnpl_settled` | Field is removed; credit-note logic that touched it is removed |

## 10. Migration steps (dev only)

1. Verify on rmax_dev2: `SELECT COUNT(*) FROM tabBNPL Settlement` — must return 0. (Confirmed during spec authoring.)
2. Cancel + delete any draft BNPL Settlement records, if found later.
3. Drop SI custom fields via fixture diff (remove from `custom_field.json`, run `bench execute frappe.custom.doctype.custom_field.custom_field.create_custom_fields` then a manual `frappe.delete_doc("Custom Field", name)` for each removed field).
4. Drop the two DocTypes: `bench execute frappe.delete_doc --kwargs '{"doctype":"DocType","name":"BNPL Settlement"}'` etc.
5. Drop the report: `frappe.delete_doc("Report", "BNPL Pending Settlement")`.
6. Pull the code change, `bench migrate`, `bench clear-cache`, supervisor signal.
7. Smoke test the surcharge-collected report and the new JE button.

## 11. Roles + permissions

JE template button: visible to `Accounts User`, `Accounts Manager`, `System Manager`. No new role. No new permission rule on Journal Entry — it relies on the standard JE write permission.

The Branch User role does not get the button (Branch User isn't part of the BNPL settlement workflow).

## 12. Files touched

| File | Change |
|---|---|
| `rmax_custom/hooks.py` | Drop `Sales Invoice-custom_bnpl_settlement` from fixtures filter; add `doctype_js` for Journal Entry; add `validate` doc_event for Journal Entry |
| `rmax_custom/setup.py` | Drop call to settlement-specific setup; keep `setup_bnpl_accounts` for clearing + fee accounts |
| `rmax_custom/bnpl_settlement_setup.py` | Strip BNPL Settlement creation paths; rename leftover helpers if needed |
| `rmax_custom/bnpl_clearing_guard.py` *(new)* | `warn_bnpl_clearing_overdraw`, `_bnpl_clearing_accounts`, `_gl_balance_excluding` |
| `rmax_custom/public/js/journal_entry_bnpl_template.js` *(new)* | Button + dialog + loader |
| `rmax_custom/api/bnpl.py` | Add `get_clearing_account_for_mop(mop, company)`; add `get_clearing_balance(account)` |
| `rmax_custom/fixtures/custom_field.json` | Remove the two settlement-link SI custom fields |
| `rmax_custom/rmax_custom/doctype/bnpl_settlement/` | Delete |
| `rmax_custom/rmax_custom/doctype/bnpl_settlement_invoice/` | Delete |
| `rmax_custom/rmax_custom/report/bnpl_pending_settlement/` | Delete |
| `rmax_custom/rmax_custom/report/bnpl_surcharge_collected/bnpl_surcharge_collected.py` | Refactor to drop Settlement linkage |

## 13. Test plan

Each passes before deploy is considered green.

1. **Unit (Python):** `_bnpl_clearing_accounts(company)` returns the configured set; empty when no MoP has surcharge.
2. **Unit (Python):** `_gl_balance_excluding(account, voucher_no)` returns 0 for an account with no GL entries; returns sum of past entries when present.
3. **Unit (Python):** `warn_bnpl_clearing_overdraw` emits `frappe.msgprint` (capture via `frappe.message_log`) when credit > balance, no message when ≤ balance.
4. **Integration (bench):** Create a Sales Invoice with Tabby payment → submit → check Tabby Clearing balance increases by uplifted amount → load BNPL Settlement template on a new JE → fill bank=100, fee=10 → balance below 110 triggers warn, allows submit.
5. **Manual UI:** Verify button hidden on submitted JEs; verify dialog filters MoPs to surcharge-only.
6. **Report:** `bnpl_surcharge_collected` returns the same totals before and after the refactor for invoices that have `custom_pos_payments_json` set.

## 14. Rollback

Revert the commit. Account heads (clearing, fee) remain. No data loss because dev had no Settlement records.

---

**End of design.**
