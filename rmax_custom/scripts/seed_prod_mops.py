"""Seed standard Modes of Payment + link Cash to the default Company account.

Idempotent. Run once on a fresh prod tenant if the ERPNext setup wizard
didn't seed them. Safe to rerun.
"""

from __future__ import annotations

import frappe


COMPANY = "Clear Light Company"

MOP_SEED = [
    # ZATCA payment-means codes (UN/EDIFACT 4461)
    {"name": "Cash", "type": "Cash", "zatca_code": "10"},
    {"name": "Bank Draft", "type": "Bank", "zatca_code": "42"},
    {"name": "Bank Transfer", "type": "Bank", "zatca_code": "30"},
    {"name": "Mada", "type": "Bank", "zatca_code": "48"},
    {"name": "Visa Card", "type": "Bank", "zatca_code": "48"},
    {"name": "Cheque", "type": "Bank", "zatca_code": "20"},
    {"name": "Wire Transfer", "type": "Bank", "zatca_code": "31"},
]


def seed():
    _ensure_modes_of_payment()
    _link_cash_to_company()
    frappe.db.commit()
    print("--- DONE ---")


def _ensure_modes_of_payment():
    has_zatca = frappe.db.has_column("Mode of Payment", "custom_zatca_payment_means_code")
    for spec in MOP_SEED:
        if frappe.db.exists("Mode of Payment", spec["name"]):
            print(f"[skip] {spec['name']} (exists)")
            continue
        try:
            doc = {
                "doctype": "Mode of Payment",
                "mode_of_payment": spec["name"],
                "type": spec["type"],
                "enabled": 1,
            }
            if has_zatca:
                doc["custom_zatca_payment_means_code"] = spec.get("zatca_code", "1")
            frappe.get_doc(doc).insert(ignore_permissions=True)
            print(f"[create] {spec['name']} ({spec['type']})")
        except Exception as e:
            print(f"[fail] {spec['name']}: {e}")


def _link_cash_to_company():
    if not frappe.db.exists("Mode of Payment", "Cash"):
        print("[skip] 'Cash' Mode of Payment missing")
        return
    cash_acc = frappe.db.get_value("Company", COMPANY, "default_cash_account")
    if not cash_acc:
        cash_acc = frappe.db.get_value(
            "Account",
            {"company": COMPANY, "account_type": "Cash", "is_group": 0},
            "name",
        )
    if not cash_acc:
        print(f"[skip] no cash account on {COMPANY}")
        return

    mop = frappe.get_doc("Mode of Payment", "Cash")
    if any(r.company == COMPANY for r in mop.accounts):
        print(f"[skip] 'Cash' MoP already has account row for {COMPANY}")
        return
    mop.append("accounts", {"company": COMPANY, "default_account": cash_acc})
    mop.flags.ignore_permissions = True
    mop.save()
    print(f"[link] 'Cash' MoP -> {cash_acc}")
