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

    def test_branch_dimension_mandatory_per_company(self):
        inter_branch._ensure_branch_accounting_dimension()

        companies = frappe.get_all("Company", pluck="name")
        self.assertGreater(len(companies), 0, "Need at least one Company in test data")

        dim_name = frappe.db.get_value("Accounting Dimension", {"document_type": "Branch"})
        for company in companies:
            row = frappe.db.get_value(
                "Accounting Dimension Detail",
                {"parent": dim_name, "company": company},
                ["mandatory_for_bs", "mandatory_for_pl", "reference_document"],
                as_dict=True,
            )
            self.assertIsNotNone(row, f"No dimension_defaults row for company {company}")
            self.assertEqual(row.mandatory_for_bs, 1)
            self.assertEqual(row.mandatory_for_pl, 1)
            self.assertEqual(row.reference_document, "Branch")


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
