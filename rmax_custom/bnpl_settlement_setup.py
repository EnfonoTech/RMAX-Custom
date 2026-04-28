"""
BNPL clearing + fee account provisioning.

Idempotent setup that runs from setup.after_migrate. For each root
Company it ensures:

  * `Tabby Clearing - <abbr>` account under Bank Accounts (account_type=Bank).
  * `Tamara Clearing - <abbr>` account under Bank Accounts (account_type=Bank).
  * `BNPL Fee Expense - <abbr>` account under Indirect Expenses.
  * Company.custom_bnpl_fee_account points at the per-company fee account.

The Mode of Payment records (`Tabby`, `Tamara`) are wired by the user
once via the Mode of Payment form: set Surcharge Percentage = 8.6957
and pick the matching Clearing Account. We do not auto-create or
mutate Mode of Payment rows here, since the customer may already have
an existing configuration we should not override.
"""

from __future__ import annotations

from typing import Optional

import frappe
from frappe.utils import flt


CLEARING_ACCOUNTS = [
	{"account_name": "Tabby Clearing", "account_type": "Bank", "root_type": "Asset"},
	{"account_name": "Tamara Clearing", "account_type": "Bank", "root_type": "Asset"},
]
FEE_ACCOUNT = {"account_name": "BNPL Fee Expense", "root_type": "Expense"}


def setup_bnpl_accounts():
	"""Idempotent provisioning per root Company."""
	if not frappe.db.exists("DocType", "Account"):
		return

	root_companies = frappe.get_all(
		"Company",
		filters=[["parent_company", "in", ["", None]]],
		fields=["name", "abbr"],
	)

	for company in root_companies:
		_ensure_clearing_accounts(company.name, company.abbr)
		fee_account_name = _ensure_fee_account(company.name, company.abbr)
		_wire_company_default_fee_account(company.name, fee_account_name)

	frappe.db.commit()


def _ensure_clearing_accounts(company: str, abbr: str):
	parent = _find_bank_parent(company, abbr)
	if not parent:
		return

	for spec in CLEARING_ACCOUNTS:
		account_name = f"{spec['account_name']} - {abbr}"
		if frappe.db.exists("Account", account_name):
			continue
		try:
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": spec["account_name"],
					"parent_account": parent,
					"company": company,
					"account_type": spec["account_type"],
					"root_type": spec["root_type"],
					"is_group": 0,
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"rmax_custom bnpl_settlement_setup: failed to create {account_name}",
			)


def _ensure_fee_account(company: str, abbr: str) -> Optional[str]:
	account_name = f"{FEE_ACCOUNT['account_name']} - {abbr}"
	if frappe.db.exists("Account", account_name):
		return account_name

	parent = _find_indirect_expenses_parent(company)
	if not parent:
		return None

	try:
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": FEE_ACCOUNT["account_name"],
				"parent_account": parent,
				"company": company,
				"account_type": "Expense Account",
				"root_type": FEE_ACCOUNT["root_type"],
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			f"rmax_custom bnpl_settlement_setup: failed to create {account_name}",
		)
		return None
	return account_name


def _wire_company_default_fee_account(company: str, fee_account: Optional[str]):
	"""Set Company.custom_bnpl_fee_account if currently empty."""
	if not fee_account:
		return
	if not frappe.db.has_column("Company", "custom_bnpl_fee_account"):
		return
	current = frappe.db.get_value("Company", company, "custom_bnpl_fee_account")
	if current:
		return
	frappe.db.set_value(
		"Company",
		company,
		"custom_bnpl_fee_account",
		fee_account,
		update_modified=False,
	)


def _find_bank_parent(company: str, abbr: str) -> Optional[str]:
	"""Locate the standard Bank Accounts group; fallback to Current Assets."""
	candidates = [
		f"Bank Accounts - {abbr}",
		f"Current Assets - {abbr}",
	]
	for name in candidates:
		if frappe.db.exists("Account", {"name": name, "company": company, "is_group": 1}):
			return name

	# As a final fallback, find any group account under root Asset.
	asset_root = frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Asset", "is_group": 1, "parent_account": ["in", ["", None]]},
		"name",
	)
	return asset_root


def _find_indirect_expenses_parent(company: str) -> Optional[str]:
	parent = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": "Indirect Expenses", "is_group": 1},
		"name",
	)
	if parent:
		return parent
	# Fallback to the Expense root.
	return frappe.db.get_value(
		"Account",
		{
			"company": company,
			"root_type": "Expense",
			"is_group": 1,
			"parent_account": ["in", ["", None]],
		},
		"name",
	)
