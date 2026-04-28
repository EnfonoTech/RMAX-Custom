"""
Soft balance guard on Journal Entries that credit BNPL clearing accounts.

The set of "BNPL clearing accounts" is the union of `default_account` values
on `Mode of Payment Account` rows whose parent Mode of Payment carries a
positive `custom_surcharge_percentage`. The set is scoped per Company.

The validator emits an orange `frappe.msgprint` (no throw) when any single
JE credits more than the live GL balance of a clearing account. Submission
is allowed — finance reviews the message and proceeds if the situation is
legitimate (refund carry-forward, manual correction, etc).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, fmt_money


ROUNDING_TOLERANCE = 0.01


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


def warn_bnpl_clearing_overdraw(doc, method=None):
    """Soft warn (no throw) when a JE credits more than the live BNPL clearing balance.

    Wired via doc_events on Journal Entry.validate. Never raises — emits an
    orange `frappe.msgprint` and lets the user proceed.
    """
    if getattr(doc, "doctype", None) != "Journal Entry":
        return
    company = getattr(doc, "company", None)
    if not company:
        return
    clearing_accounts = _bnpl_clearing_accounts(company)
    if not clearing_accounts:
        return

    seen: dict[str, float] = {}
    for row in (doc.get("accounts") or []):
        account = getattr(row, "account", None)
        if account not in clearing_accounts:
            continue
        credit = flt(getattr(row, "credit_in_account_currency", 0))
        if credit <= 0:
            continue
        seen[account] = seen.get(account, 0.0) + credit

    if not seen:
        return

    for account, credit in seen.items():
        live_balance = _gl_balance_excluding(account, getattr(doc, "name", None))
        if credit > live_balance + ROUNDING_TOLERANCE:
            ccy = (
                frappe.db.get_value("Account", account, "account_currency") or ""
            )
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
