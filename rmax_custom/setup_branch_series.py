"""Branch-wise naming series provisioning.

Concept (mirrors Flames' "Document Naming Series"):

  Each Branch carries a `custom_doc_prefix` (e.g. WJ-, AZZ-).  For every
  GL/stock-side doctype on the system we build a per-doctype series
  template `<PREFIX><DOC>-.YYYY.-.####` and:

    1. Insert a `Branch Naming Series` child row on the Branch master
       (parent_doctype=<doctype>, naming_series=<template>).  Returns
       get a separate row tagged `use_for_return=1`.

    2. Append the same template to the doctype's `naming_series`
       Property Setter `options` (newline-separated list).  This exposes
       every branch's series in the form's dropdown so operators can
       see them all + Frappe validates a saved doc against the list.

  The `set_naming_series_from_branch` hook reads (1) at `before_insert`
  to auto-pick the right series for the logged-in user.  (2) is just
  for UI completeness + validation.

  Idempotent.  Safe to re-run on every after_migrate.
"""

from __future__ import annotations

from typing import Iterable

import frappe


# (doctype, abbrev, supports_return)
SERIES_TARGETS = [
    ("Sales Invoice", "INV", True),     # CN suffix used for return variant
    ("Delivery Note", "DN", True),
    ("Purchase Receipt", "PR", False),
    ("Purchase Invoice", "PI", True),
    ("Payment Entry", "PE", False),
    ("Stock Entry", "SE", False),
    ("Stock Reconciliation", "SR", False),
    ("Quotation", "QT", False),
    ("Material Request", "MR", False),
    ("Stock Transfer", "ST", False),
    ("Journal Entry", "JV", False),
    ("Sales Order", "SO", False),
    ("Purchase Order", "PO", False),
    ("Damage Slip", "DS", False),
    ("Damage Transfer", "DT", False),
    ("No VAT Sale", "NVS", False),
]
RETURN_SUFFIX_OVERRIDES = {
    # Default suffix on the return variant of a doctype, if different.
    "Sales Invoice": "CN",      # Credit Note
    "Delivery Note": "DRN",     # Delivery Return Note
    "Purchase Invoice": "DN",   # Debit Note
}


def _series_template(prefix: str, abbrev: str) -> str:
    """Build `<PREFIX><DOC>-.YYYY.-.####` template.  prefix already ends with '-'."""
    return f"{prefix}{abbrev}-.YYYY.-.####"


def _ensure_branch_row(branch_name: str, doctype: str, series: str, use_for_return: bool) -> None:
    existing = frappe.db.exists(
        "Branch Naming Series",
        {
            "parent": branch_name,
            "parenttype": "Branch",
            "parent_doctype": doctype,
            "use_for_return": 1 if use_for_return else 0,
        },
    )
    if existing:
        # Refresh the series template if it drifted
        if frappe.db.get_value("Branch Naming Series", existing, "naming_series") != series:
            frappe.db.set_value("Branch Naming Series", existing, "naming_series", series, update_modified=False)
        return
    # Append directly to child table via SQL — avoids loading whole Branch
    # doc just to add a single row.
    parent_doc = frappe.get_doc("Branch", branch_name)
    parent_doc.append("custom_naming_series_table", {
        "parent_doctype": doctype,
        "naming_series": series,
        "use_for_return": 1 if use_for_return else 0,
    })
    parent_doc.save(ignore_permissions=True)


def _push_to_property_setter_options(doctype: str, series_list: Iterable[str]) -> None:
    """Append every series in series_list to the doctype's naming_series
    Property Setter options.  Frappe stores options newline-delimited.
    """
    if not frappe.db.exists("DocType", doctype):
        return
    meta = frappe.get_meta(doctype)
    field = meta.get_field("naming_series")
    if not field:
        return

    current_opts = (field.options or "").split("\n")
    current = [o.strip() for o in current_opts if o and o.strip()]

    desired = list(current)
    for s in series_list:
        if s not in desired:
            desired.append(s)

    if desired == current:
        return

    new_opts = "\n".join(desired)

    ps_name = frappe.db.get_value(
        "Property Setter",
        {
            "doc_type": doctype,
            "field_name": "naming_series",
            "property": "options",
        },
        "name",
    )
    if ps_name:
        frappe.db.set_value("Property Setter", ps_name, "value", new_opts, update_modified=False)
    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            "doc_type": doctype,
            "field_name": "naming_series",
            "property": "options",
            "property_type": "Text",
            "value": new_opts,
        }).insert(ignore_permissions=True)
    frappe.clear_cache(doctype=doctype)


def setup_branch_series() -> None:
    """Idempotent.  Walks every Branch with a custom_doc_prefix, then
    every doctype in SERIES_TARGETS, creates the Branch Naming Series
    row, and registers the series in the doctype's Property Setter.
    """
    branches = frappe.get_all(
        "Branch",
        filters={"custom_doc_prefix": ["!=", ""]},
        fields=["name", "custom_doc_prefix"],
    )
    if not branches:
        return

    by_doctype: dict[str, list[str]] = {}
    for br in branches:
        prefix = (br.custom_doc_prefix or "").strip()
        if not prefix:
            continue
        for dt, abbrev, supports_return in SERIES_TARGETS:
            if not frappe.db.exists("DocType", dt):
                continue
            primary = _series_template(prefix, abbrev)
            _ensure_branch_row(br.name, dt, primary, use_for_return=False)
            by_doctype.setdefault(dt, []).append(primary)

            if supports_return:
                ret_abbrev = RETURN_SUFFIX_OVERRIDES.get(dt, abbrev + "R")
                ret_template = _series_template(prefix, ret_abbrev)
                _ensure_branch_row(br.name, dt, ret_template, use_for_return=True)
                by_doctype.setdefault(dt, []).append(ret_template)

    for dt, series_list in by_doctype.items():
        _push_to_property_setter_options(dt, series_list)

    frappe.db.commit()
