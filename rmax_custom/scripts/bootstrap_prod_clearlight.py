"""
Production bootstrap script for the Clear Light Company tenant on
SaaS Server 1 (`rmax.enfonoerp.com`).

Idempotent. Safe to rerun. Creates:
  - Branch tree:                Head Office (group) → 14 leaves
  - Cost Center tree:           Head Office - <abbr> (group) → 14 leaves
  - Warehouse tree:             Head Office - <abbr> (group) → 14 leaves
  - Branch Configuration row    per branch (with company)
  - Naming-series options       per transactional doctype (HQ-, WJ-, ...)
  - Stock Settings:             valuation_method = "Moving Average"
  - Branch.custom_doc_prefix    per branch (drives auto-pick at insert)

Run:
    bench --site rmax.enfonoerp.com execute rmax_custom.scripts.bootstrap_prod_clearlight.bootstrap

Read-only dry-run:
    bench --site rmax.enfonoerp.com execute rmax_custom.scripts.bootstrap_prod_clearlight.bootstrap --kwargs '{"dry_run": True}'
"""

from __future__ import annotations

import frappe

COMPANY_NAME = "Clear Light Company"

# Branch tuples: (display_name, doc_prefix)
BRANCHES = [
    ("HQ Awtad",          "HQ-"),
    ("Warehouse Jeddah",  "WJ-"),
    ("Warehouse Bahrah",  "WB-"),
    ("Warehouse Riyadh",  "WR-"),
    ("Warehouse Malaz",   "WM-"),
    ("Ghurab Office",     "GO-"),
    ("Azzizziyah",        "AZZ-"),
    ("Ghurab Showroom",   "GS-"),
    ("Dammam Sales",      "DS-"),
    ("CL1 Malaz",         "CL1-"),
    ("CL2 Malaz",         "CL2-"),
    ("Riyadh Sales",      "RS-"),
    ("Reem",              "RM-"),
    ("Taif Sales",        "TF-"),
]

HO_BRANCH_NAME = "Head Office"
HO_PREFIX = "HO-"

# Doctypes whose `naming_series` field gets the per-branch options appended.
NAMING_SERIES_TARGETS = [
    "Sales Invoice",
    "Quotation",
    "Delivery Note",
    "Purchase Invoice",
    "Purchase Receipt",
    "Payment Entry",
    "Material Request",
    "Stock Entry",
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def bootstrap(dry_run: bool | int | str = False):
    dry = _is_truthy(dry_run)
    log = _make_logger(dry)

    company_abbr = _resolve_company_abbr(log)
    log(f"Company abbreviation resolved: {company_abbr}")

    setup_stock_settings(log, dry)
    setup_branches(log, dry)
    setup_cost_centers(company_abbr, log, dry)
    setup_warehouses(company_abbr, log, dry)
    setup_branch_configurations(log, dry)
    setup_naming_series(log, dry)

    if not dry:
        frappe.db.commit()

    log("--- DONE ---")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_truthy(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "y", "t")
    return False


def _make_logger(dry: bool):
    prefix = "[DRY] " if dry else ""

    def _log(msg: str):
        print(f"{prefix}{msg}")

    return _log


def _resolve_company_abbr(log) -> str:
    if not frappe.db.exists("Company", COMPANY_NAME):
        frappe.throw(
            f"Company '{COMPANY_NAME}' does not exist. Create it first via the Company Setup wizard."
        )
    abbr = frappe.db.get_value("Company", COMPANY_NAME, "abbr")
    if not abbr:
        frappe.throw(f"Company '{COMPANY_NAME}' has no abbreviation. Set one via the form.")
    return abbr


# ---------------------------------------------------------------------------
# Stock Settings
# ---------------------------------------------------------------------------


def setup_stock_settings(log, dry):
    current = frappe.db.get_single_value("Stock Settings", "valuation_method")
    if current == "Moving Average":
        log("Stock Settings: valuation_method already 'Moving Average' — skipped")
        return
    log(f"Stock Settings: valuation_method '{current}' → 'Moving Average'")
    if dry:
        return
    settings = frappe.get_single("Stock Settings")
    settings.valuation_method = "Moving Average"
    settings.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Branch tree
# ---------------------------------------------------------------------------


def setup_branches(log, dry):
    """Branch is a NestedSet doctype on Frappe v15 — supports parent_branch + is_group."""
    # 1. Head Office (group) — parent of every leaf branch.
    if not frappe.db.exists("Branch", HO_BRANCH_NAME):
        log(f"Branch: create '{HO_BRANCH_NAME}' (group)")
        if not dry:
            frappe.get_doc({
                "doctype": "Branch",
                "branch": HO_BRANCH_NAME,
                "is_group": 1,
                "custom_doc_prefix": HO_PREFIX,
            }).insert(ignore_permissions=True)
    else:
        log(f"Branch '{HO_BRANCH_NAME}' exists — checking is_group + prefix")
        updates = {}
        if not frappe.db.get_value("Branch", HO_BRANCH_NAME, "is_group"):
            updates["is_group"] = 1
        if not frappe.db.get_value("Branch", HO_BRANCH_NAME, "custom_doc_prefix"):
            updates["custom_doc_prefix"] = HO_PREFIX
        if updates and not dry:
            frappe.db.set_value("Branch", HO_BRANCH_NAME, updates, update_modified=False)

    # 2. Leaf branches under HO.
    for name, prefix in BRANCHES:
        if frappe.db.exists("Branch", name):
            current_prefix = frappe.db.get_value("Branch", name, "custom_doc_prefix") or ""
            if current_prefix != prefix and not dry:
                frappe.db.set_value("Branch", name, "custom_doc_prefix", prefix, update_modified=False)
            log(f"Branch '{name}' exists — prefix={prefix}")
            continue

        log(f"Branch: create '{name}' (parent={HO_BRANCH_NAME}, prefix={prefix})")
        if dry:
            continue
        try:
            frappe.get_doc({
                "doctype": "Branch",
                "branch": name,
                "parent_branch": HO_BRANCH_NAME,
                "is_group": 0,
                "custom_doc_prefix": prefix,
            }).insert(ignore_permissions=True)
        except Exception:
            # Some Frappe Branch implementations are flat (no NestedSet).
            # Fall back to the bare branch+prefix without parent.
            frappe.log_error(
                frappe.get_traceback(),
                f"rmax_custom: branch insert with parent failed; falling back for {name}",
            )
            frappe.get_doc({
                "doctype": "Branch",
                "branch": name,
                "custom_doc_prefix": prefix,
            }).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Cost Center tree
# ---------------------------------------------------------------------------


def setup_cost_centers(abbr: str, log, dry):
    root_name = _root_account_or_cc(
        doctype="Cost Center", company=COMPANY_NAME, is_group=1
    )
    if not root_name:
        log(f"Cost Center root not found for {COMPANY_NAME} — skipping")
        return

    ho_group_name = f"{HO_BRANCH_NAME} - {abbr}"
    _ensure_cost_center(ho_group_name, root_name, abbr, is_group=1, log=log, dry=dry)

    for name, _prefix in BRANCHES:
        cc_name = f"{name} - {abbr}"
        _ensure_cost_center(cc_name, ho_group_name, abbr, is_group=0, log=log, dry=dry)


def _ensure_cost_center(name: str, parent: str, abbr: str, is_group: int, log, dry):
    if frappe.db.exists("Cost Center", name):
        log(f"Cost Center '{name}' exists")
        return
    log(f"Cost Center: create '{name}' (parent={parent}, group={is_group})")
    if dry:
        return
    cc = frappe.get_doc({
        "doctype": "Cost Center",
        "cost_center_name": name.split(" - ")[0],
        "parent_cost_center": parent,
        "company": COMPANY_NAME,
        "is_group": is_group,
    })
    cc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Warehouse tree
# ---------------------------------------------------------------------------


def setup_warehouses(abbr: str, log, dry):
    root_name = _root_account_or_cc(
        doctype="Warehouse", company=COMPANY_NAME, is_group=1
    )
    if not root_name:
        log(f"Warehouse root not found for {COMPANY_NAME} — skipping")
        return

    ho_group_name = f"{HO_BRANCH_NAME} - {abbr}"
    _ensure_warehouse(ho_group_name, root_name, abbr, is_group=1, log=log, dry=dry)

    for name, _prefix in BRANCHES:
        wh_name = f"{name} - {abbr}"
        _ensure_warehouse(wh_name, ho_group_name, abbr, is_group=0, log=log, dry=dry)


def _ensure_warehouse(name: str, parent: str, abbr: str, is_group: int, log, dry):
    if frappe.db.exists("Warehouse", name):
        log(f"Warehouse '{name}' exists")
        return
    log(f"Warehouse: create '{name}' (parent={parent}, group={is_group})")
    if dry:
        return
    wh = frappe.get_doc({
        "doctype": "Warehouse",
        "warehouse_name": name.split(" - ")[0],
        "parent_warehouse": parent,
        "company": COMPANY_NAME,
        "is_group": is_group,
    })
    wh.insert(ignore_permissions=True)


def _root_account_or_cc(doctype: str, company: str, is_group: int) -> str | None:
    """Return the topmost group node of a tree doctype for the given company."""
    rows = frappe.get_all(
        doctype,
        filters={"company": company, "is_group": is_group, "lft": 1},
        pluck="name",
    )
    if rows:
        return rows[0]
    rows = frappe.get_all(
        doctype,
        filters={"company": company, "is_group": is_group},
        order_by="lft asc",
        pluck="name",
        limit=1,
    )
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Branch Configuration
# ---------------------------------------------------------------------------


def setup_branch_configurations(log, dry):
    all_names = [HO_BRANCH_NAME] + [name for name, _ in BRANCHES]
    for name in all_names:
        if frappe.db.exists("Branch Configuration", name):
            log(f"Branch Configuration '{name}' exists")
            continue
        log(f"Branch Configuration: create '{name}' (company={COMPANY_NAME})")
        if dry:
            continue
        try:
            frappe.get_doc({
                "doctype": "Branch Configuration",
                "branch": name,
                "company": COMPANY_NAME,
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"rmax_custom: Branch Configuration insert failed for {name}",
            )


# ---------------------------------------------------------------------------
# Naming series options
# ---------------------------------------------------------------------------


def setup_naming_series(log, dry):
    """Append per-branch naming-series options to every transactional doctype.

    A user belonging to a given branch will get the matching option auto-
    selected by the `set_naming_series_from_branch` before_insert hook.
    """
    series_lines = [f"{prefix}.YYYY.-.####" for _, prefix in BRANCHES]
    series_lines.insert(0, f"{HO_PREFIX}.YYYY.-.####")  # HO group as fallback

    for doctype in NAMING_SERIES_TARGETS:
        existing_opts = _current_naming_options(doctype)
        merged = _merge_naming_options(existing_opts, series_lines)
        if merged == existing_opts:
            log(f"Naming series for {doctype}: already up-to-date")
            continue
        log(f"Naming series for {doctype}: appending {len(series_lines)} prefix options")
        if dry:
            continue
        _write_naming_options(doctype, merged)
        frappe.clear_cache(doctype=doctype)


def _current_naming_options(doctype: str) -> str:
    ps_value = frappe.db.get_value(
        "Property Setter",
        {
            "doc_type": doctype,
            "field_name": "naming_series",
            "property": "options",
        },
        "value",
    )
    if ps_value is not None:
        return ps_value or ""

    meta = frappe.get_meta(doctype)
    field = meta.get_field("naming_series")
    return (field.options if field else "") or ""


def _merge_naming_options(existing: str, additions: list[str]) -> str:
    existing_lines = [l for l in (existing or "").split("\n") if l]
    seen = set(existing_lines)
    merged = list(existing_lines)
    for line in additions:
        if line not in seen:
            merged.append(line)
            seen.add(line)
    return "\n".join(merged)


def _write_naming_options(doctype: str, value: str):
    name = frappe.db.get_value(
        "Property Setter",
        {
            "doc_type": doctype,
            "field_name": "naming_series",
            "property": "options",
        },
        "name",
    )
    if name:
        frappe.db.set_value("Property Setter", name, "value", value)
        return
    frappe.get_doc({
        "doctype": "Property Setter",
        "doctype_or_field": "DocField",
        "doc_type": doctype,
        "field_name": "naming_series",
        "property": "options",
        "property_type": "Text",
        "value": value,
    }).insert(ignore_permissions=True)
