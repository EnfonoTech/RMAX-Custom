"""
Phase-2 prod restructure: mirrors the manually-restructured Cost Center
tree onto Warehouse, adds Damage warehouses, and seeds KSA standard
Sales / Purchase tax templates.

Idempotent. Safe to rerun.

Final Warehouse + Cost Center shape:

    Head Office - CL                 (group)
        HQ Awtad - CL                (leaf, direct HO ops)
        Warehouse Jeddah - CL        (leaf, direct HO ops)
        Warehouse Bahrah - CL        (leaf)
        Warehouse Riyadh - CL        (leaf)
        Warehouse Malaz - CL         (leaf)
        Branches - CL                (group)
            Ghurab Office - CL
            Azzizziyah - CL
            Ghurab Showroom - CL
            Dammam Sales - CL
            CL1 Malaz - CL
            CL2 Malaz - CL
            Riyadh Sales - CL
            Reem - CL
            Taif Sales - CL
        Damage - CL                  (group, warehouse only)
            Damage Jeddah - CL
            Damage Riyadh - CL

Run:
    bench --site rmax.enfonoerp.com console
        from rmax_custom.scripts.restructure_prod_clearlight import restructure
        restructure()
"""

from __future__ import annotations

import frappe


COMPANY = "Clear Light Company"
ABBR = "CL"

HO_GROUP = f"Head Office - {ABBR}"
BRANCHES_GROUP = f"Branches - {ABBR}"
DAMAGE_GROUP = f"Damage - {ABBR}"

DIRECT_HO_BRANCHES = [
    "HQ Awtad",
    "Warehouse Jeddah",
    "Warehouse Bahrah",
    "Warehouse Riyadh",
    "Warehouse Malaz",
]
SUB_BRANCHES = [
    "Ghurab Office",
    "Azzizziyah",
    "Ghurab Showroom",
    "Dammam Sales",
    "CL1 Malaz",
    "CL2 Malaz",
    "Riyadh Sales",
    "Reem",
    "Taif Sales",
]
DAMAGE_BRANCHES = ["Damage Jeddah", "Damage Riyadh"]


def restructure():
    print("=== Warehouse tree ===")
    _restructure_warehouses()
    print("=== Damage warehouses ===")
    _create_damage_warehouses()
    print("=== Sales / Purchase Tax Templates ===")
    _create_tax_templates()
    frappe.db.commit()
    print("--- DONE ---")


# ---------------------------------------------------------------------------
# Warehouse restructure (mirror Cost Center)
# ---------------------------------------------------------------------------


def _restructure_warehouses():
    # Ensure Branches - CL group exists under Head Office - CL.
    if not frappe.db.exists("Warehouse", BRANCHES_GROUP):
        wh = frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": "Branches",
            "parent_warehouse": HO_GROUP,
            "company": COMPANY,
            "is_group": 1,
        })
        wh.insert(ignore_permissions=True)
        print(f"  [create group] {BRANCHES_GROUP}")
    else:
        print(f"  [skip] {BRANCHES_GROUP} exists")

    # Move 9 sub-branches under Branches - CL
    for branch in SUB_BRANCHES:
        wh_name = f"{branch} - {ABBR}"
        if not frappe.db.exists("Warehouse", wh_name):
            print(f"  [warn] {wh_name} missing — skipping")
            continue
        current_parent = frappe.db.get_value("Warehouse", wh_name, "parent_warehouse")
        if current_parent == BRANCHES_GROUP:
            print(f"  [skip] {wh_name} already under {BRANCHES_GROUP}")
            continue
        wh = frappe.get_doc("Warehouse", wh_name)
        wh.parent_warehouse = BRANCHES_GROUP
        wh.flags.ignore_permissions = True
        wh.save()
        print(f"  [move] {wh_name} -> {BRANCHES_GROUP}")


def _create_damage_warehouses():
    # Damage - CL group under Head Office - CL
    if not frappe.db.exists("Warehouse", DAMAGE_GROUP):
        wh = frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": "Damage",
            "parent_warehouse": HO_GROUP,
            "company": COMPANY,
            "is_group": 1,
        })
        wh.insert(ignore_permissions=True)
        print(f"  [create group] {DAMAGE_GROUP}")
    else:
        print(f"  [skip] {DAMAGE_GROUP} exists")

    # Two leaf warehouses
    for branch in DAMAGE_BRANCHES:
        wh_name = f"{branch} - {ABBR}"
        if frappe.db.exists("Warehouse", wh_name):
            print(f"  [skip] {wh_name} exists")
            continue
        wh = frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": branch,
            "parent_warehouse": DAMAGE_GROUP,
            "company": COMPANY,
            "is_group": 0,
        })
        wh.insert(ignore_permissions=True)
        print(f"  [create] {wh_name}")


# ---------------------------------------------------------------------------
# Tax Templates (KSA VAT 15%)
# ---------------------------------------------------------------------------


SALES_TEMPLATE_NAME = f"KSA VAT 15% - {ABBR}"
PURCHASE_TEMPLATE_NAME = f"KSA VAT 15% Input - {ABBR}"

OUTPUT_VAT_ACCOUNT_NAME = "VAT Output 15%"  # under Tax Liabilities
INPUT_VAT_ACCOUNT_NAME = "VAT Input 15%"    # under Tax Assets


def _create_tax_templates():
    output_vat = _ensure_tax_account(
        OUTPUT_VAT_ACCOUNT_NAME,
        root_type="Liability",
        parent_label="Duties and Taxes",
        account_type="Tax",
    )
    input_vat = _ensure_tax_account(
        INPUT_VAT_ACCOUNT_NAME,
        root_type="Asset",
        parent_label="Tax Assets",
        account_type="Tax",
    )

    if output_vat:
        _ensure_sales_taxes_template(output_vat)
    if input_vat:
        _ensure_purchase_taxes_template(input_vat)


def _ensure_tax_account(label: str, root_type: str, parent_label: str, account_type: str) -> str | None:
    full_name = f"{label} - {ABBR}"
    if frappe.db.exists("Account", full_name):
        print(f"  [skip] {full_name} exists")
        return full_name

    parent = _find_parent_group(root_type, parent_label)
    if not parent:
        print(f"  [warn] no parent group for {label}")
        return None

    acc = frappe.get_doc({
        "doctype": "Account",
        "account_name": label,
        "parent_account": parent,
        "company": COMPANY,
        "is_group": 0,
        "root_type": root_type,
        "account_type": account_type,
    })
    acc.insert(ignore_permissions=True)
    print(f"  [create account] {full_name} (parent={parent})")
    return full_name


def _find_parent_group(root_type: str, label: str) -> str | None:
    # Try literal `<Label> - <abbr>` first
    candidate = f"{label} - {ABBR}"
    if frappe.db.exists("Account", {"name": candidate, "company": COMPANY, "is_group": 1}):
        return candidate
    # Numbered CoA — match by account_name
    row = frappe.db.get_value(
        "Account",
        {
            "company": COMPANY,
            "account_name": label,
            "is_group": 1,
            "root_type": root_type,
        },
        "name",
    )
    if row:
        return row
    # Last resort: company root for the matching root_type
    res = frappe.db.sql(
        """
        SELECT name FROM `tabAccount`
        WHERE company = %s AND root_type = %s AND is_group = 1
          AND (parent_account IS NULL OR parent_account = '')
        LIMIT 1
        """,
        (COMPANY, root_type),
    )
    return res[0][0] if res else None


def _ensure_sales_taxes_template(output_vat_account: str):
    if frappe.db.exists("Sales Taxes and Charges Template", SALES_TEMPLATE_NAME):
        print(f"  [skip] {SALES_TEMPLATE_NAME} exists")
        return
    doc = frappe.get_doc({
        "doctype": "Sales Taxes and Charges Template",
        "title": "KSA VAT 15%",
        "company": COMPANY,
        "is_default": 1,
        "taxes": [
            {
                "charge_type": "On Net Total",
                "account_head": output_vat_account,
                "description": "VAT 15% (KSA Standard Rate)",
                "rate": 15.0,
                "included_in_print_rate": 0,
            }
        ],
    })
    doc.insert(ignore_permissions=True)
    print(f"  [create] {SALES_TEMPLATE_NAME}")


def _ensure_purchase_taxes_template(input_vat_account: str):
    if frappe.db.exists("Purchase Taxes and Charges Template", PURCHASE_TEMPLATE_NAME):
        print(f"  [skip] {PURCHASE_TEMPLATE_NAME} exists")
        return
    doc = frappe.get_doc({
        "doctype": "Purchase Taxes and Charges Template",
        "title": "KSA VAT 15% Input",
        "company": COMPANY,
        "is_default": 1,
        "taxes": [
            {
                "category": "Total",
                "add_deduct_tax": "Add",
                "charge_type": "On Net Total",
                "account_head": input_vat_account,
                "description": "Input VAT 15% (KSA Standard Rate, deductible)",
                "rate": 15.0,
                "included_in_print_rate": 0,
            }
        ],
    })
    doc.insert(ignore_permissions=True)
    print(f"  [create] {PURCHASE_TEMPLATE_NAME}")
