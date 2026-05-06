"""Tests for rmax_custom.print_helpers."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from rmax_custom.print_helpers import get_invoice_title


class TestInvoiceTitleResolution(FrappeTestCase):
    """get_invoice_title returns ('Tax Invoice', 'فاتورة ضريبية') by default and
    flips to the simplified pair when the customer is B2C OR has empty tax_id."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.b2b_name = _ensure_customer(
            "RMAX Test B2B", tax_id="300000000000003", custom_is_b2c=0
        )
        cls.b2c_flag_name = _ensure_customer(
            "RMAX Test B2C Flagged", tax_id="300000000000003", custom_is_b2c=1
        )
        cls.empty_vat_name = _ensure_customer(
            "RMAX Test Empty VAT", tax_id="", custom_is_b2c=0
        )

    def _stub_invoice(self, customer_name):
        return frappe._dict(customer=customer_name)

    def test_b2b_with_vat_returns_tax_invoice(self):
        en, ar = get_invoice_title(self._stub_invoice(self.b2b_name))
        self.assertEqual(en, "Tax Invoice")
        self.assertEqual(ar, "فاتورة ضريبية")

    def test_b2c_flagged_returns_simplified(self):
        en, ar = get_invoice_title(self._stub_invoice(self.b2c_flag_name))
        self.assertEqual(en, "Simplified Tax Invoice")
        self.assertEqual(ar, "فاتورة ضريبية مبسطة")

    def test_empty_vat_returns_simplified(self):
        en, ar = get_invoice_title(self._stub_invoice(self.empty_vat_name))
        self.assertEqual(en, "Simplified Tax Invoice")
        self.assertEqual(ar, "فاتورة ضريبية مبسطة")


def _ensure_customer(name, *, tax_id, custom_is_b2c):
    if frappe.db.exists("Customer", name):
        c = frappe.get_doc("Customer", name)
    else:
        c = frappe.new_doc("Customer")
        c.customer_name = name
        c.customer_group = frappe.db.get_value(
            "Customer Group", {"is_group": 0}, "name"
        ) or "All Customer Groups"
        c.territory = frappe.db.get_value(
            "Territory", {"is_group": 0}, "name"
        ) or "All Territories"
    c.tax_id = tax_id
    c.custom_is_b2c = custom_is_b2c
    c.save(ignore_permissions=True)
    return c.name
