"""
One-shot migration: drop BNPL Settlement DocTypes, BNPL Pending Settlement
report, and the two SI custom fields that linked invoices to Settlements.

Idempotent — re-running is safe; it only deletes what still exists.

Run with:
    bench --site rmax_dev2 execute rmax_custom.migrations.drop_bnpl_settlement.run
"""

from __future__ import annotations

import frappe


DOCTYPES_TO_DROP = ["BNPL Settlement Invoice", "BNPL Settlement"]
REPORT_TO_DROP = "BNPL Pending Settlement"
CUSTOM_FIELDS_TO_DROP = [
    "Sales Invoice-custom_bnpl_settlement",
    "Sales Invoice-custom_bnpl_settled",
]


def run():
    _drop_custom_fields()
    _drop_report()
    _drop_doctypes()
    frappe.db.commit()
    print("drop_bnpl_settlement: complete")


def _drop_custom_fields():
    for name in CUSTOM_FIELDS_TO_DROP:
        if frappe.db.exists("Custom Field", name):
            frappe.delete_doc("Custom Field", name, force=True)
            print(f"  - dropped Custom Field: {name}")


def _drop_report():
    if frappe.db.exists("Report", REPORT_TO_DROP):
        frappe.delete_doc("Report", REPORT_TO_DROP, force=True)
        print(f"  - dropped Report: {REPORT_TO_DROP}")


def _drop_doctypes():
    for dt in DOCTYPES_TO_DROP:
        if frappe.db.exists("DocType", dt):
            count = frappe.db.count(dt)
            if count:
                frappe.db.sql(f"DELETE FROM `tab{dt}`")
                print(f"  - cleared {count} rows from tab{dt}")
            frappe.delete_doc("DocType", dt, force=True, ignore_missing=True)
            print(f"  - dropped DocType: {dt}")
