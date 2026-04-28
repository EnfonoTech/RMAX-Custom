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


def wire_bnpl_modes_of_payment(surcharge_percentage: float = 8.6957):
	"""One-shot helper: wire Tabby + Tamara Mode of Payment to their
	clearing accounts and set the surcharge percentage.

	Called manually via `bench execute` after the auto-created clearing
	accounts exist. Idempotent — re-running does not duplicate child rows.

	Not part of after_migrate so that customer Mode of Payment records are
	never silently mutated. Run explicitly when go-live config is required.
	"""
	targets = [
		("Tabby", "Tabby Clearing"),
		("Tamara", "Tamara Clearing"),
	]
	# Include child companies — clearing accounts already replicate to
	# their per-company namespace via ERPNext's standard account sync, so
	# the MoP Account child table needs a row for every Company.
	companies = frappe.get_all("Company", fields=["name", "abbr"])

	results = []
	for mop_name, base_clearing in targets:
		if not frappe.db.exists("Mode of Payment", mop_name):
			payload = {
				"doctype": "Mode of Payment",
				"mode_of_payment": mop_name,
				"type": "Bank",
				"enabled": 1,
			}
			# ksa_compliance bolts on a mandatory ZATCA payment means code
			# field — use code 10 (cash payment) to match the existing
			# Tabby record, since Tabby/Tamara act like cash from the
			# customer's perspective at point-of-sale.
			if frappe.db.has_column("Mode of Payment", "custom_zatca_payment_means_code"):
				payload["custom_zatca_payment_means_code"] = "10"
			try:
				frappe.get_doc(payload).insert(ignore_permissions=True)
			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					f"rmax_custom: failed to create MoP {mop_name}",
				)
				continue

		mop = frappe.get_doc("Mode of Payment", mop_name)
		mop.custom_surcharge_percentage = flt(surcharge_percentage)

		# Prefer the RMAX (abbr R) clearing account on the parent if available.
		rmax_clearing = f"{base_clearing} - R"
		if frappe.db.exists("Account", rmax_clearing):
			mop.custom_bnpl_clearing_account = rmax_clearing
		else:
			# Fallback: first available clearing account.
			for c in companies:
				candidate = f"{base_clearing} - {c.abbr}"
				if frappe.db.exists("Account", candidate):
					mop.custom_bnpl_clearing_account = candidate
					break

		# Rebuild Accounts child rows from scratch so old Receivable links die.
		new_rows = []
		for c in companies:
			clearing = f"{base_clearing} - {c.abbr}"
			if not frappe.db.exists("Account", clearing):
				continue
			new_rows.append({"company": c.name, "default_account": clearing})

		mop.set("accounts", [])
		for r in new_rows:
			mop.append("accounts", r)

		mop.save(ignore_permissions=True)
		results.append(
			f"{mop_name}: surcharge={mop.custom_surcharge_percentage} "
			f"clearing={mop.custom_bnpl_clearing_account} rows={len(mop.accounts)}"
		)

	frappe.db.commit()
	for line in results:
		print(line)
	return results


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
