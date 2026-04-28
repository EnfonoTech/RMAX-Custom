"""Inter-Branch Receivables & Payables — Phase 1 Foundation.

Single-company multi-branch GL: enables branch as a mandatory accounting
dimension enforced per-Company at the GL-posting layer, manages the
Inter-Branch chart-of-accounts groups + lazy leaves, auto-injects balancing
inter-branch legs into Journal Entries, and generates a companion inter-branch
JE for cross-branch Stock Transfers.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate  # noqa: F401  — used in Tasks 6+


def _ensure_branch_accounting_dimension() -> None:
    """Enable Branch as an Accounting Dimension and mark it mandatory per Company.

    ERPNext enforces mandatory accounting dimensions at the GL-posting layer:
    when `mandatory_for_bs` and `mandatory_for_pl` are set on the per-Company
    row of `dimension_defaults`, every Balance-Sheet and P&L GL Entry for that
    company is rejected without a Branch value. This covers Journal Entry,
    Stock Entry, Payment Entry, and every other GL-posting doctype.

    Idempotent: safe to re-run from after_migrate.
    """
    dim_name = frappe.db.get_value("Accounting Dimension", {"document_type": "Branch"})
    if dim_name:
        dim = frappe.get_doc("Accounting Dimension", dim_name)
    else:
        dim = frappe.new_doc("Accounting Dimension")
        dim.document_type = "Branch"
        dim.disabled = 0
        dim.insert(ignore_permissions=True)

    if dim.disabled:
        dim.disabled = 0

    existing_companies = {row.company for row in (dim.dimension_defaults or [])}

    for company in frappe.get_all("Company", pluck="name"):
        if company in existing_companies:
            for row in dim.dimension_defaults:
                if row.company == company:
                    row.mandatory_for_bs = 1
                    row.mandatory_for_pl = 1
                    row.reference_document = "Branch"
        else:
            dim.append(
                "dimension_defaults",
                {
                    "company": company,
                    "reference_document": "Branch",
                    "mandatory_for_bs": 1,
                    "mandatory_for_pl": 1,
                },
            )

    dim.save(ignore_permissions=True)
    frappe.db.commit()


INTER_BRANCH_RECEIVABLE_LABEL = "Inter-Branch Receivable"
INTER_BRANCH_PAYABLE_LABEL = "Inter-Branch Payable"


def _company_abbr(company: str) -> str:
    return frappe.db.get_value("Company", company, "abbr")


def _find_parent_group(company: str, root_type: str, fallback_label: str) -> str:
    """Return the canonical parent group account name for a given root_type.

    Asset → "Current Assets - <abbr>" if it exists, else falls back to the
    company's root Asset group. Liability → "Current Liabilities - <abbr>".
    """
    abbr = _company_abbr(company)
    candidate = f"{fallback_label} - {abbr}"
    if frappe.db.exists("Account", candidate):
        return candidate

    # Fallback: the company root for the matching root_type
    root = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": root_type, "is_group": 1, "parent_account": ""},
        "name",
    )
    if not root:
        frappe.throw(_("Cannot locate root {0} group for company {1}").format(root_type, company))
    return root


def _ensure_group_account(company: str, label: str, root_type: str, parent: str) -> str:
    abbr = _company_abbr(company)
    name = f"{label} - {abbr}"
    if frappe.db.exists("Account", name):
        return name

    acc = frappe.new_doc("Account")
    acc.account_name = label
    acc.company = company
    acc.parent_account = parent
    acc.is_group = 1
    acc.root_type = root_type
    if root_type == "Asset":
        acc.account_type = "Receivable"
    elif root_type == "Liability":
        acc.account_type = "Payable"
    acc.insert(ignore_permissions=True)
    return acc.name


def _ensure_inter_branch_groups(company: str) -> tuple[str, str]:
    """Create the two inter-branch parent groups under Current Assets / Current Liabilities."""
    rec_parent = _find_parent_group(company, "Asset", "Current Assets")
    pay_parent = _find_parent_group(company, "Liability", "Current Liabilities")

    receivable = _ensure_group_account(company, INTER_BRANCH_RECEIVABLE_LABEL, "Asset", rec_parent)
    payable = _ensure_group_account(company, INTER_BRANCH_PAYABLE_LABEL, "Liability", pay_parent)
    return receivable, payable


def setup_inter_branch_foundation() -> None:
    """Idempotent entrypoint called from setup.after_migrate."""
    _ensure_branch_accounting_dimension()
    for company_name in frappe.get_all("Company", pluck="name"):
        _ensure_inter_branch_groups(company_name)
