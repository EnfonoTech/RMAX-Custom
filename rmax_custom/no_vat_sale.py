# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""Setup helpers for the No VAT Sale workflow.

Idempotent one-time configuration, run from after_migrate:
* 'No VAT Price' price list.
* Per root-company GL accounts `Current Account - Naseef (N)` and
  `Damage Written Off (N)`, and auto-link them to the Company's
  custom_novat_naseef_account / custom_novat_cogs_account fields.
* Ensure Mode of Payment 'Cash' has an Accounts row per Company
  pointing at the Company's default_cash_account.

Nothing is overwritten once set — manual client edits to any of the
targets survive every upgrade.
"""

from typing import Optional

import frappe


NO_VAT_PRICE_LIST = "No VAT Price"

# Account names shipped under each company
NASEEF_ACCOUNT_NAME = "Current Account - Naseef (N)"
COGS_ACCOUNT_NAME = "Damage Written Off (N)"

# Parent groups we look under on each Company's CoA
LIABILITY_PARENTS = ("Current Liabilities", "Accounts Payable")
EXPENSE_PARENTS = ("Indirect Expenses",)

MODE_OF_PAYMENT_NAME = "Cash"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def setup_no_vat_sale():
	_ensure_price_list()
	_ensure_accounts_per_company()
	_ensure_mode_of_payment_accounts()


# ---------------------------------------------------------------------------
# Price list
# ---------------------------------------------------------------------------


def _ensure_price_list():
	if frappe.db.exists("Price List", NO_VAT_PRICE_LIST):
		return
	try:
		frappe.get_doc({
			"doctype": "Price List",
			"price_list_name": NO_VAT_PRICE_LIST,
			"currency": frappe.db.get_single_value("Global Defaults", "default_currency") or "SAR",
			"enabled": 1,
			"buying": 0,
			"selling": 1,
		}).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"rmax_custom: failed to create No VAT Price list",
		)


# ---------------------------------------------------------------------------
# GL accounts per Company + link on Company fields
# ---------------------------------------------------------------------------


def _ensure_accounts_per_company():
	"""Create Naseef + COGS accounts on every root Company and link them
	to the Company's NO VAT custom fields. Safe + idempotent."""
	root_companies = frappe.get_all(
		"Company",
		filters=[["parent_company", "in", ["", None]]],
		fields=["name", "abbr"],
	)

	for company in root_companies:
		try:
			naseef = _ensure_account(
				company=company.name,
				abbr=company.abbr,
				account_name=NASEEF_ACCOUNT_NAME,
				parent_candidates=LIABILITY_PARENTS,
				root_type="Liability",
				account_type="",
			)
			cogs = _ensure_account(
				company=company.name,
				abbr=company.abbr,
				account_name=COGS_ACCOUNT_NAME,
				parent_candidates=EXPENSE_PARENTS,
				root_type="Expense",
				account_type="Expense Account",
			)

			# Link on Company if the Company custom fields are still blank
			if naseef and not frappe.db.get_value(
				"Company", company.name, "custom_novat_naseef_account"
			):
				frappe.db.set_value(
					"Company",
					company.name,
					"custom_novat_naseef_account",
					naseef,
					update_modified=False,
				)
			if cogs and not frappe.db.get_value(
				"Company", company.name, "custom_novat_cogs_account"
			):
				frappe.db.set_value(
					"Company",
					company.name,
					"custom_novat_cogs_account",
					cogs,
					update_modified=False,
				)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"rmax_custom: No VAT account setup failed for {company.name}",
			)

	frappe.db.commit()


def _ensure_account(
	company: str,
	abbr: str,
	account_name: str,
	parent_candidates: tuple,
	root_type: str,
	account_type: str,
) -> Optional[str]:
	"""Ensure a leaf Account with the given name exists under the first
	matching parent group for the company. Returns the full account name
	(`<account_name> - <abbr>`) or None if no suitable parent found."""
	full_name = f"{account_name} - {abbr}"
	if frappe.db.exists("Account", full_name):
		return full_name

	parent = _find_parent_group(company, parent_candidates, root_type)
	if not parent:
		# Last resort: first group account of the right root_type
		parent = frappe.db.get_value(
			"Account",
			{"company": company, "root_type": root_type, "is_group": 1},
			"name",
		)
	if not parent:
		return None

	doc = frappe.get_doc({
		"doctype": "Account",
		"account_name": account_name,
		"parent_account": parent,
		"company": company,
		"is_group": 0,
		"root_type": root_type,
		"account_type": account_type,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def _find_parent_group(company: str, candidates: tuple, root_type: str) -> Optional[str]:
	for label in candidates:
		name = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"account_name": label,
				"is_group": 1,
				"root_type": root_type,
			},
			"name",
		)
		if name:
			return name
	return None


# ---------------------------------------------------------------------------
# Mode of Payment → default account per Company
# ---------------------------------------------------------------------------


def _ensure_mode_of_payment_accounts():
	"""Every Company needs a `Mode of Payment Account` row under 'Cash'
	so the No VAT Sale form can auto-fill cash_account."""
	if not frappe.db.exists("Mode of Payment", MODE_OF_PAYMENT_NAME):
		return

	try:
		mop = frappe.get_doc("Mode of Payment", MODE_OF_PAYMENT_NAME)
	except Exception:
		return

	companies = frappe.get_all("Company", fields=["name", "default_cash_account"])
	dirty = False

	for company in companies:
		has_row = any(row.company == company.name for row in mop.accounts)
		if has_row:
			continue

		cash_account = company.default_cash_account
		if not cash_account:
			# Try a sensible fallback: any Cash account for the company
			cash_account = frappe.db.get_value(
				"Account",
				{
					"company": company.name,
					"account_type": "Cash",
					"is_group": 0,
				},
				"name",
			)
		if not cash_account:
			continue

		mop.append("accounts", {
			"company": company.name,
			"default_account": cash_account,
		})
		dirty = True

	if dirty:
		try:
			mop.flags.ignore_permissions = True
			mop.save()
			frappe.db.commit()
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				"rmax_custom: failed to update Mode of Payment Cash accounts",
			)
