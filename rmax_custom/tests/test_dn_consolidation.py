"""Tests for rmax_custom.api.delivery_note.consolidate_dns_to_si — mixed
DN + Return DN net-off consolidation path."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from rmax_custom.api.delivery_note import consolidate_dns_to_si


class TestConsolidateDnsToSi(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = _ensure_customer("RMAX Consol Test")
        cls.item = _ensure_item("RMAX-CONSOL-TEST-ITEM")
        cls.company = _pick_default_company()
        cls.warehouse = _pick_default_warehouse(cls.company)

    def test_mixed_batch_nets_off(self):
        dn1 = _make_submitted_dn(self.customer, self.item, self.company,
                                 self.warehouse, qty=100, rate=10)
        dn2 = _make_submitted_dn(self.customer, self.item, self.company,
                                 self.warehouse, qty=50, rate=10)
        dn3 = _make_submitted_dn(self.customer, self.item, self.company,
                                 self.warehouse, qty=30, rate=10)
        ret = _make_submitted_return_dn(dn1, qty=40)

        si_name = consolidate_dns_to_si([dn1.name, dn2.name, dn3.name, ret.name])

        si = frappe.get_doc("Sales Invoice", si_name)
        self.assertEqual(si.docstatus, 0)
        self.assertEqual(si.customer, self.customer)
        self.assertEqual(si.update_stock, 0)
        # net = 100 + 50 + 30 - 40 = 140
        total_qty = sum(flt(r.qty) for r in si.items if r.item_code == self.item)
        self.assertEqual(total_qty, 140)

    def test_all_positive_batch_works_like_classic_consolidation(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=10, rate=10)
        si_name = consolidate_dns_to_si([dn.name])
        si = frappe.get_doc("Sales Invoice", si_name)
        self.assertEqual(flt(si.items[0].qty), 10)

    def test_mismatched_customer_throws(self):
        c1 = _ensure_customer("RMAX Consol Cust A")
        c2 = _ensure_customer("RMAX Consol Cust B")
        dn_a = _make_submitted_dn(c1, self.item, self.company,
                                  self.warehouse, qty=5, rate=10)
        dn_b = _make_submitted_dn(c2, self.item, self.company,
                                  self.warehouse, qty=5, rate=10)
        with self.assertRaises(frappe.ValidationError):
            consolidate_dns_to_si([dn_a.name, dn_b.name])

    def test_empty_input_throws(self):
        with self.assertRaises(frappe.ValidationError):
            consolidate_dns_to_si([])

    def test_already_consolidated_dn_throws(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=5, rate=10)
        consolidate_dns_to_si([dn.name])
        with self.assertRaises(frappe.ValidationError):
            consolidate_dns_to_si([dn.name])

    def test_si_cancel_clears_stamp(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=5, rate=10)
        si_name = consolidate_dns_to_si([dn.name])
        si = frappe.get_doc("Sales Invoice", si_name)
        si.submit()
        si.cancel()
        self.assertFalse(
            frappe.db.get_value("Delivery Note", dn.name, "custom_consolidated_si")
        )


# --- fixtures helpers ---

def _ensure_customer(name):
    if frappe.db.exists("Customer", name):
        return name
    c = frappe.new_doc("Customer")
    c.customer_name = name
    c.customer_group = frappe.db.get_value(
        "Customer Group", {"is_group": 0}, "name"
    ) or "All Customer Groups"
    c.territory = frappe.db.get_value(
        "Territory", {"is_group": 0}, "name"
    ) or "All Territories"
    c.save(ignore_permissions=True)
    return c.name


def _ensure_item(item_code):
    if frappe.db.exists("Item", item_code):
        return item_code
    i = frappe.new_doc("Item")
    i.item_code = item_code
    i.item_name = item_code
    i.item_group = frappe.db.get_value(
        "Item Group", {"is_group": 0}, "name"
    ) or "All Item Groups"
    i.stock_uom = "Nos"
    i.is_stock_item = 0  # avoid bin/valuation setup in unit tests
    i.save(ignore_permissions=True)
    return i.name


def _pick_default_company():
    return frappe.db.get_single_value("Global Defaults", "default_company") \
        or frappe.db.get_value("Company", {}, "name")


def _pick_default_warehouse(company):
    return frappe.db.get_value(
        "Warehouse", {"company": company, "is_group": 0}, "name"
    )


def _make_submitted_dn(customer, item, company, warehouse, *, qty, rate):
    dn = frappe.new_doc("Delivery Note")
    dn.customer = customer
    dn.company = company
    dn.set_warehouse = warehouse
    dn.append("items", {
        "item_code": item,
        "qty": qty,
        "rate": rate,
        "warehouse": warehouse,
        "uom": "Nos",
    })
    dn.insert(ignore_permissions=True)
    dn.submit()
    return dn


def _make_submitted_return_dn(parent_dn, *, qty):
    ret = frappe.new_doc("Delivery Note")
    ret.customer = parent_dn.customer
    ret.company = parent_dn.company
    ret.set_warehouse = parent_dn.set_warehouse
    ret.is_return = 1
    ret.return_against = parent_dn.name
    src_row = parent_dn.items[0]
    ret.append("items", {
        "item_code": src_row.item_code,
        "qty": -1 * abs(qty),
        "rate": src_row.rate,
        "warehouse": src_row.warehouse,
        "uom": src_row.uom,
        "delivery_note": parent_dn.name,
        "dn_detail": src_row.name,
    })
    ret.insert(ignore_permissions=True)
    ret.submit()
    return ret
