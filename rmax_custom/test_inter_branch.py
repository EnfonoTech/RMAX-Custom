"""Tests for inter-branch foundation module."""
from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

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

    def _make_je_template(self, posting_date: str = "2026-04-28"):
        """Build an UNSAVED Journal Entry that posts rent in Riyadh paid by HO bank."""
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

        per_branch: dict[str, float] = {}
        for row in je.accounts:
            br = row.branch or ""
            per_branch[br] = per_branch.get(br, 0.0) + flt(row.debit_in_account_currency) - flt(row.credit_in_account_currency)
        for br, bal in per_branch.items():
            self.assertEqual(round(bal, 2), 0.0, f"Branch {br} unbalanced: {bal}")

    def test_three_branch_je_rejected(self):
        je = self._make_je_template()
        rent_acc = je.accounts[0].account
        je.append(
            "accounts",
            {"account": rent_acc, "debit_in_account_currency": 500, "branch": "Jeddah"},
        )
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

        first_snapshot = [
            (r.account, flt(r.debit_in_account_currency), flt(r.credit_in_account_currency),
             r.branch, getattr(r, "custom_auto_inserted", 0))
            for r in je.accounts
        ]

        inter_branch.auto_inject_inter_branch_legs(je)

        second_snapshot = [
            (r.account, flt(r.debit_in_account_currency), flt(r.credit_in_account_currency),
             r.branch, getattr(r, "custom_auto_inserted", 0))
            for r in je.accounts
        ]

        self.assertEqual(first_snapshot, second_snapshot, "Re-running injector changed JE rows")

    def test_first_alphabetic_branch_as_debtor(self):
        """Cover the path where sorted-first branch has positive delta (it's the debtor)."""
        # Use "Alpha" (sorted first) as debtor and "Zeta" (sorted last) as creditor
        for br in ("Alpha", "Zeta"):
            if not frappe.db.exists("Branch", br):
                d = frappe.new_doc("Branch")
                d.branch = br
                d.insert(ignore_permissions=True)

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
        # Alpha is debtor (consumes Zeta's bank); rent expense booked under Alpha
        je.append(
            "accounts",
            {"account": rent_acc, "debit_in_account_currency": 750, "branch": "Alpha"},
        )
        je.append(
            "accounts",
            {"account": bank_acc, "credit_in_account_currency": 750, "branch": "Zeta"},
        )

        inter_branch.auto_inject_inter_branch_legs(je)

        injected = [row for row in je.accounts if getattr(row, "custom_auto_inserted", 0)]
        self.assertEqual(len(injected), 2)

        # Alpha must end up with the credit-side payable leg (debtor's credit)
        alpha_inj = [r for r in injected if r.branch == "Alpha"]
        zeta_inj = [r for r in injected if r.branch == "Zeta"]
        self.assertEqual(len(alpha_inj), 1)
        self.assertEqual(len(zeta_inj), 1)
        self.assertEqual(flt(alpha_inj[0].credit_in_account_currency), 750.0)
        self.assertEqual(flt(zeta_inj[0].debit_in_account_currency), 750.0)

        # Per-branch balance check
        per_branch: dict[str, float] = {}
        for row in je.accounts:
            br = row.branch or ""
            per_branch[br] = per_branch.get(br, 0.0) + flt(row.debit_in_account_currency) - flt(row.credit_in_account_currency)
        for br, bal in per_branch.items():
            self.assertEqual(round(bal, 2), 0.0, f"Branch {br} unbalanced: {bal}")
