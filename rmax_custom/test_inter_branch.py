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
