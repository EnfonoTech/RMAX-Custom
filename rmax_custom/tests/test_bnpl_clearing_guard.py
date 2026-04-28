"""
Unit tests for rmax_custom.bnpl_clearing_guard.

Run via: bench --site rmax_dev2 run-tests --module rmax_custom.tests.test_bnpl_clearing_guard
"""

import frappe
import unittest
from unittest.mock import MagicMock

from rmax_custom.bnpl_clearing_guard import (
    _bnpl_clearing_accounts,
    _gl_balance_excluding,
    warn_bnpl_clearing_overdraw,
)


class TestBnplClearingAccounts(unittest.TestCase):
    def setUp(self):
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


class TestGLBalanceExcluding(unittest.TestCase):
    def test_zero_for_account_with_no_entries(self):
        company = frappe.db.get_value("Company", {"is_group": 0}, "name")
        abbr = frappe.db.get_value("Company", company, "abbr")
        acc_label = "__Test BNPL Balance"
        acc_name = f"{acc_label} - {abbr}"
        if not frappe.db.exists("Account", acc_name):
            parent = frappe.db.get_value(
                "Account",
                {"company": company, "is_group": 1, "root_type": "Asset"},
                "name",
            )
            acc = frappe.get_doc({
                "doctype": "Account",
                "account_name": acc_label,
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
        doc.doctype = "Journal Entry"
        doc.company = self.company
        doc.name = "__TEST_JE_DRAFT__"
        row = MagicMock()
        row.account = self.tabby_clearing
        row.account_currency = "SAR"
        row.credit_in_account_currency = credit_amount
        row.debit_in_account_currency = 0
        doc.accounts = [row]
        # MagicMock.get returns a MagicMock by default — make it return the list
        doc.get = lambda key, default=None: doc.accounts if key == "accounts" else default
        return doc

    def test_no_message_when_credit_below_balance(self):
        frappe.message_log = []
        warn_bnpl_clearing_overdraw(self._build_doc(0))
        self.assertEqual(frappe.message_log, [])

    def test_message_when_credit_exceeds_balance(self):
        frappe.message_log = []
        warn_bnpl_clearing_overdraw(self._build_doc(10**9))
        joined = "\n".join(str(m) for m in frappe.message_log)
        self.assertIn("BNPL Clearing Balance Exceeded", joined)
