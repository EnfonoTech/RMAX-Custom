"""Tests for rmax_custom.api.delivery_note:
 - consolidate_dns_to_si       — mixed DN + Return DN net-off consolidation
 - create_consolidated_return_dn_from_dns — RMAX-style Return DN from many DNs
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from rmax_custom.api.delivery_note import (
    consolidate_dns_to_si,
    create_consolidated_return_dn_from_dns,
)


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

    def test_clubbed_dn_billing_status_flips_on_submit_and_reverts(self):
        # The net-off SI omits SI Item.delivery_note, so ERPNext's billing calc
        # can't flip the clubbed DNs. on_submit must mark them Completed; cancel
        # must revert to To Bill.
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=5, rate=10)
        self.assertEqual(
            frappe.db.get_value("Delivery Note", dn.name, "status"), "To Bill"
        )
        si = frappe.get_doc("Sales Invoice", consolidate_dns_to_si([dn.name]))
        si.submit()
        dn.reload()
        self.assertEqual(flt(dn.per_billed), 100)
        self.assertEqual(dn.status, "Completed")
        si.cancel()
        dn.reload()
        self.assertEqual(dn.status, "To Bill")

    def test_consolidated_si_inherits_dn_price_list(self):
        # Consolidated SI must carry the source DN's selling price list (e.g.
        # "Inter Company Price"), not fall back to the customer/default list.
        pl = _ensure_selling_price_list("RMAX Consol PL")
        dn = frappe.new_doc("Delivery Note")
        dn.customer = self.customer
        dn.company = self.company
        dn.set_warehouse = self.warehouse
        dn.selling_price_list = pl
        dn.append("items", {
            "item_code": self.item, "qty": 3, "rate": 10,
            "warehouse": self.warehouse, "uom": "Nos",
        })
        dn.insert(ignore_permissions=True)
        dn.submit()
        si = frappe.get_doc("Sales Invoice", consolidate_dns_to_si([dn.name]))
        self.assertEqual(si.selling_price_list, pl)

    def test_draft_si_delete_clears_stamp_and_succeeds(self):
        # Reproduces the bug: a DRAFT consolidated SI stamps the DN via
        # custom_consolidated_si; deleting it must clear the stamp (on_trash)
        # so the link-integrity check doesn't block the delete.
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=5, rate=10)
        si_name = consolidate_dns_to_si([dn.name])
        self.assertEqual(
            frappe.db.get_value("Delivery Note", dn.name, "custom_consolidated_si"),
            si_name,
        )
        frappe.delete_doc("Sales Invoice", si_name)
        self.assertFalse(frappe.db.exists("Sales Invoice", si_name))
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


def _ensure_selling_price_list(name):
    if not frappe.db.exists("Price List", name):
        pl = frappe.new_doc("Price List")
        pl.price_list_name = name
        pl.selling = 1
        pl.enabled = 1
        pl.currency = "SAR"
        pl.insert(ignore_permissions=True)
    return name


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


class TestConsolidatedReturnDn(FrappeTestCase):
    """Tests for create_consolidated_return_dn_from_dns."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = _ensure_customer("RMAX RDN Test")
        cls.item = _ensure_item("RMAX-RDN-TEST-ITEM")
        cls.company = _pick_default_company()
        cls.warehouse = _pick_default_warehouse(cls.company)

    def test_two_dns_consolidate_to_one_return_dn(self):
        dn1 = _make_submitted_dn(self.customer, self.item, self.company,
                                 self.warehouse, qty=10, rate=100)
        dn2 = _make_submitted_dn(self.customer, self.item, self.company,
                                 self.warehouse, qty=5, rate=100)

        rdn_name = create_consolidated_return_dn_from_dns([dn1.name, dn2.name])
        rdn = frappe.get_doc("Delivery Note", rdn_name)

        self.assertEqual(rdn.is_return, 1)
        self.assertFalse(rdn.return_against)
        self.assertEqual(rdn.customer, self.customer)
        self.assertEqual(len(rdn.items), 2)
        # qty negated
        self.assertEqual(flt(rdn.items[0].qty), -10)
        self.assertEqual(flt(rdn.items[1].qty), -5)
        # source stamps set
        self.assertEqual(
            frappe.db.get_value("Delivery Note", dn1.name, "custom_return_dn"), rdn_name
        )
        self.assertEqual(
            frappe.db.get_value("Delivery Note", dn2.name, "custom_return_dn"), rdn_name
        )

    def test_cross_customer_throws(self):
        c1 = _ensure_customer("RMAX RDN A")
        c2 = _ensure_customer("RMAX RDN B")
        dn_a = _make_submitted_dn(c1, self.item, self.company,
                                  self.warehouse, qty=2, rate=10)
        dn_b = _make_submitted_dn(c2, self.item, self.company,
                                  self.warehouse, qty=2, rate=10)
        with self.assertRaises(frappe.ValidationError):
            create_consolidated_return_dn_from_dns([dn_a.name, dn_b.name])

    def test_already_linked_throws(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=5, rate=10)
        create_consolidated_return_dn_from_dns([dn.name])
        with self.assertRaises(frappe.ValidationError):
            create_consolidated_return_dn_from_dns([dn.name])

    def test_return_dn_input_throws(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=5, rate=10)
        rdn_name = create_consolidated_return_dn_from_dns([dn.name])
        # try to "return a return"
        with self.assertRaises(frappe.ValidationError):
            create_consolidated_return_dn_from_dns([rdn_name])

    def test_cancel_clears_stamp(self):
        dn = _make_submitted_dn(self.customer, self.item, self.company,
                                self.warehouse, qty=3, rate=10)
        rdn_name = create_consolidated_return_dn_from_dns([dn.name])
        rdn = frappe.get_doc("Delivery Note", rdn_name)
        rdn.submit()
        rdn.cancel()
        self.assertFalse(
            frappe.db.get_value("Delivery Note", dn.name, "custom_return_dn")
        )


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
