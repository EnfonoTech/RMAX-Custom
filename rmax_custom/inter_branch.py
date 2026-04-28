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


def setup_inter_branch_foundation() -> None:
    """Idempotent entrypoint called from setup.after_migrate."""
    _ensure_branch_accounting_dimension()
