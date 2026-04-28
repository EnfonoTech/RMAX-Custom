"""
Unit tests for rmax_custom.api.bnpl whitelisted endpoints.

Run via: bench --site rmax_dev2 run-tests --module rmax_custom.tests.test_bnpl_api
"""

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
        result = get_clearing_account_for_mop(
            mop="__nonexistent__", company=self.company
        )
        self.assertIsNone(result.get("account"))

    def test_empty_mop_returns_none(self):
        result = get_clearing_account_for_mop(mop="", company=self.company)
        self.assertIsNone(result.get("account"))

    def test_clearing_balance_zero_for_unknown_account(self):
        bal = get_clearing_balance(account="__nope__")
        self.assertEqual(bal, 0.0)

    def test_clearing_balance_zero_for_empty_account(self):
        bal = get_clearing_balance(account="")
        self.assertEqual(bal, 0.0)
