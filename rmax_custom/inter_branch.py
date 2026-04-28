"""Inter-Branch Receivables & Payables — Phase 1 Foundation.

Single-company multi-branch GL: enables branch as a mandatory accounting
dimension, manages the Inter-Branch chart-of-accounts groups + lazy leaves,
auto-injects balancing inter-branch legs into Journal Entries, and generates
a companion inter-branch JE for cross-branch Stock Transfers.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

# DocTypes that must carry a non-null Branch on every GL-posting line.
MANDATORY_BRANCH_DOCTYPES = (
    "Journal Entry",
    "Stock Entry",
    "Payment Entry",
)


def _ensure_branch_accounting_dimension() -> None:
    """Enable Branch as an Accounting Dimension and mark mandatory.

    Idempotent: safe to re-run from after_migrate.
    """
    dim_name = frappe.db.get_value("Accounting Dimension", {"document_type": "Branch"})
    if not dim_name:
        dim = frappe.new_doc("Accounting Dimension")
        dim.document_type = "Branch"
        dim.disabled = 0
        dim.insert(ignore_permissions=True)
        dim_name = dim.name

    dim = frappe.get_doc("Accounting Dimension", dim_name)

    existing_targets = {row.document_type for row in dim.dimension_defaults or []}
    for dt in MANDATORY_BRANCH_DOCTYPES:
        if dt in existing_targets:
            for row in dim.dimension_defaults:
                if row.document_type == dt:
                    row.mandatory_for_bs = 1
                    row.mandatory_for_pl = 1
        else:
            dim.append(
                "dimension_defaults",
                {
                    "document_type": dt,
                    "mandatory_for_bs": 1,
                    "mandatory_for_pl": 1,
                    "reference_document": "Branch",
                },
            )

    dim.save(ignore_permissions=True)
    frappe.db.commit()


def setup_inter_branch_foundation() -> None:
    """Idempotent entrypoint called from setup.after_migrate."""
    _ensure_branch_accounting_dimension()
