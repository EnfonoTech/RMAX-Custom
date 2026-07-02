# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

from __future__ import annotations
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class InterBranchStockTransfer(Document):

    def validate(self):
        self._set_item_warehouses_from_header()
        self._set_default_taxes_and_charges()

    def _set_item_warehouses_from_header(self):
        """Push header warehouse defaults to item rows that have no row-level value."""
        for item in self.items or []:
            if self.from_warehouse and not item.s_warehouse:
                item.s_warehouse = self.from_warehouse
            if self.to_warehouse and not item.t_warehouse:
                item.t_warehouse = self.to_warehouse

    def _set_default_taxes_and_charges(self):
        """Default to the company's default Sales Taxes and Charges Template, if unset."""
        if self.is_new() and self.company and not self.taxes_and_charges:
            self.taxes_and_charges = frappe.db.get_value(
                "Sales Taxes and Charges Template", {"is_default": 1, "company": self.company}
            )

    def before_submit(self):
        self._validate_warehouses()
        self._validate_stock_availability()

    def _validate_warehouses(self):
        for item in self.items or []:
            if not item.s_warehouse:
                frappe.throw(
                    _("Row {0}: Source Warehouse is required for item {1}").format(
                        item.idx, item.item_code
                    )
                )
            if not item.t_warehouse:
                frappe.throw(
                    _("Row {0}: Target Warehouse is required for item {1}").format(
                        item.idx, item.item_code
                    )
                )
            if item.s_warehouse == item.t_warehouse:
                frappe.throw(
                    _("Row {0}: Source and Target Warehouse cannot be the same for item {1}").format(
                        item.idx, item.item_code
                    )
                )

    def _validate_stock_availability(self):
        wh_item_qty: dict[tuple[str, str], float] = defaultdict(float)
        for item in self.items or []:
            if item.item_code and item.s_warehouse:
                wh_item_qty[(item.s_warehouse, item.item_code)] += flt(item.qty)

        shortages = []
        for (warehouse, item_code), needed in wh_item_qty.items():
            actual = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": item_code, "warehouse": warehouse},
                    "actual_qty",
                )
            )
            if actual < needed:
                shortages.append({
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "needed": needed,
                    "available": actual,
                })

        if shortages:
            msg = _("Insufficient stock in source warehouse for the following items:")
            msg += "<br><br><table class='table table-bordered table-sm'>"
            msg += "<thead><tr><th>{}</th><th>{}</th><th>{}</th><th>{}</th></tr></thead><tbody>".format(
                _("Item Code"), _("Source Warehouse"), _("Required Qty"), _("Available Qty")
            )
            for s in shortages:
                msg += "<tr><td>{}</td><td>{}</td><td>{}</td><td style='color:red;font-weight:bold'>{}</td></tr>".format(
                    s["item_code"], s["warehouse"], s["needed"], s["available"]
                )
            msg += "</tbody></table>"
            frappe.throw(msg, title=_("Insufficient Stock"))

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def on_submit(self):
        source_branch, target_branch = self._resolve_branches_or_throw()
        self._create_stock_entry(source_branch, target_branch)
        if self.customer:
            self._create_delivery_note(target_branch)
        try:
            self._create_journal_entry(source_branch, target_branch)
        except Exception:
            frappe.log_error(
                title="Inter-Branch companion JE failed (IBST)",
                message=frappe.get_traceback(),
            )
            raise

    def _resolve_branches_or_throw(self) -> tuple[str, str]:
        """Resolve (source_branch, target_branch) from Branch Configuration warehouse mapping.

        Both warehouses must be mapped, or GL posting for the companion Stock
        Entry / Delivery Note fails deep inside submit() with an opaque
        "Accounting Dimension Branch is required" error instead of this
        actionable one.
        """
        from rmax_custom.inter_branch import resolve_warehouse_branch

        source_branch = resolve_warehouse_branch(self.from_warehouse)
        target_branch = resolve_warehouse_branch(self.to_warehouse)

        if not source_branch or not target_branch:
            frappe.throw(
                _(
                    "Branch could not be determined for one or both warehouses.<br><br>"
                    "Go to <b>Branch Configuration</b> and add:<br>"
                    "• <b>{0}</b> under the Source Branch's Warehouse table<br>"
                    "• <b>{1}</b> under the Target Branch's Warehouse table"
                ).format(self.from_warehouse or "—", self.to_warehouse or "—"),
                title=_("Warehouse Not Mapped to Branch"),
            )
        return source_branch, target_branch

    def _create_journal_entry(
        self, source_branch: str | None = None, target_branch: str | None = None
    ) -> str | None:
        """Create and submit the inter-branch companion JE for this IBST.

        Identical pattern to create_companion_inter_branch_je_for_stock_transfer:
            Dr  Due from <target_branch>  (branch = source_branch)
            Cr  Due to <source_branch>    (branch = target_branch)
        """
        from rmax_custom.inter_branch import get_or_create_inter_branch_account

        if source_branch is None or target_branch is None:
            source_branch, target_branch = self._resolve_branches_or_throw()

        if source_branch == target_branch:
            return None

        # Amount from the submitted SE; fall back to item rows.
        amount = 0.0
        if self.stock_entry:
            se_rows = frappe.get_all(
                "Stock Entry Detail",
                filters={"parent": self.stock_entry},
                fields=["basic_amount"],
            )
            amount = round(sum(flt(r.basic_amount) for r in se_rows), 2)
        if not amount:
            amount = round(
                sum(
                    flt(getattr(item, "basic_amount", None)) or (flt(item.qty) * flt(item.basic_rate))
                    for item in (self.items or [])
                ),
                2,
            )
        if not amount:
            return None

        company = self.company
        src_receivable = get_or_create_inter_branch_account(company, target_branch, "receivable")
        tgt_payable = get_or_create_inter_branch_account(company, source_branch, "payable")

        company_currency = frappe.db.get_value("Company", company, "default_currency")
        src_currency = frappe.db.get_value("Account", src_receivable, "account_currency") or company_currency
        tgt_currency = frappe.db.get_value("Account", tgt_payable, "account_currency") or company_currency

        je = frappe.new_doc("Journal Entry")
        je.posting_date = self.posting_date
        je.company = company
        je.voucher_type = "Journal Entry"
        je.custom_source_doctype = "Inter Branch Stock Transfer"
        je.custom_source_docname = self.name
        je.user_remark = _("Inter-Branch obligation from Inter Branch Stock Transfer {0}").format(self.name)
        je.append("accounts", {
            "account": src_receivable,
            "account_currency": src_currency,
            "exchange_rate": 1,
            "debit_in_account_currency": amount,
            "debit": amount,
            "branch": source_branch,
            "custom_auto_inserted": 1,
            "custom_source_doctype": "Inter Branch Stock Transfer",
            "custom_source_docname": self.name,
        })
        je.append("accounts", {
            "account": tgt_payable,
            "account_currency": tgt_currency,
            "exchange_rate": 1,
            "credit_in_account_currency": amount,
            "credit": amount,
            "branch": target_branch,
            "custom_auto_inserted": 1,
            "custom_source_doctype": "Inter Branch Stock Transfer",
            "custom_source_docname": self.name,
        })
        je.flags.skip_inter_branch_injection = True
        je.flags.ignore_permissions = True
        je.insert(ignore_permissions=True)
        je.submit()

        self.db_set("journal_entry", je.name, notify=True)
        frappe.msgprint(
            _('Journal Entry <a href="/app/journal-entry/{0}">{0}</a> created').format(je.name),
            alert=True,
            indicator="green",
        )
        return je.name

    def _create_stock_entry(self, source_branch: str, target_branch: str):
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Transfer"
        se.company = self.company
        se.branch = source_branch
        se.set_posting_time = 1
        se.posting_date = self.posting_date
        se.posting_time = self.posting_time
        se.from_warehouse = self.from_warehouse
        se.to_warehouse = self.to_warehouse
        se.remarks = _("Created from Inter Branch Stock Transfer: {0}").format(self.name)

        for item in self.items or []:
            se.append("items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "uom": item.uom,
                "conversion_factor": item.conversion_factor or 1,
                "s_warehouse": item.s_warehouse or self.from_warehouse,
                "t_warehouse": item.t_warehouse or self.to_warehouse,
                "basic_rate": item.basic_rate,
                "allow_zero_valuation_rate": item.allow_zero_valuation_rate,
                "serial_no": item.serial_no,
                "batch_no": item.batch_no,
                # Both legs are stamped with source_branch so GL insert passes the
                # mandatory-dimension check; the target leg is corrected below.
                "branch": source_branch,
            })

        # Prevent the SE on_submit hook from creating a second inter-branch JE.
        # The IBST on_submit drives JE creation directly (same pattern as Stock Transfer).
        se.flags.from_stock_transfer = True
        se.flags.ignore_permissions = True
        se.insert(ignore_permissions=True)
        se.flags.from_stock_transfer = True  # re-set after insert, consumed on submit
        se.flags.ignore_permissions = True
        se.submit()

        if source_branch != target_branch:
            # on_stock_entry_submit (which normally does this) is skipped for SEs
            # flagged from_stock_transfer, so re-tag the target warehouse's GL
            # leg(s) here instead.
            from rmax_custom.inter_branch import _retag_se_gl_entries

            _retag_se_gl_entries(se, source_branch, target_branch)

        self.db_set("stock_entry", se.name, notify=True)
        frappe.msgprint(
            _('Stock Entry <a href="/app/stock-entry/{0}">{0}</a> created').format(se.name),
            alert=True,
            indicator="green",
        )

    def _create_delivery_note(self, target_branch: str | None = None):
        if target_branch is None:
            target_branch = self._resolve_branches_or_throw()[1]

        from rmax_custom.inter_branch import resolve_branch_cost_center

        target_cost_center = resolve_branch_cost_center(target_branch)

        dn = frappe.new_doc("Delivery Note")
        dn.customer = self.customer
        dn.company = self.company
        dn.branch = target_branch
        dn.cost_center = target_cost_center
        dn.set_posting_time = 1
        dn.posting_date = self.posting_date
        dn.posting_time = self.posting_time
        dn.set_warehouse = self.to_warehouse
        dn.custom_ibst = self.name
        dn.remarks = _("Created from Inter Branch Stock Transfer: {0}").format(self.name)

        for item in self.items or []:
            dn.append("items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "uom": item.uom,
                "warehouse": item.t_warehouse or self.to_warehouse,
                "rate": item.basic_rate,
                "cost_center": target_cost_center,
                "description": item.description or item.item_name,
                "branch": target_branch,
            })

        if self.taxes_and_charges:
            from erpnext.controllers.accounts_controller import get_taxes_and_charges

            dn.taxes_and_charges = self.taxes_and_charges
            dn.extend(
                "taxes",
                get_taxes_and_charges("Sales Taxes and Charges Template", self.taxes_and_charges),
            )

        dn.flags.ignore_permissions = True
        dn.insert(ignore_permissions=True)
        dn.submit()

        self.db_set("delivery_note", dn.name, notify=True)
        frappe.msgprint(
            _('Delivery Note <a href="/app/delivery-note/{0}">{0}</a> created').format(dn.name),
            alert=True,
            indicator="green",
        )


    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def on_cancel(self):
        self._cancel_companion_je()
        self._cancel_linked_delivery_note()
        self._cancel_linked_stock_entry()

    def _cancel_companion_je(self):
        try:
            je_names = frappe.db.sql_list(
                """
                SELECT DISTINCT je.name
                FROM `tabJournal Entry` je
                INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
                WHERE jea.custom_source_doctype = 'Inter Branch Stock Transfer'
                  AND jea.custom_source_docname = %s
                  AND je.docstatus = 1
                """,
                (self.name,),
            )
            for je_name in je_names:
                je_doc = frappe.get_doc("Journal Entry", je_name)
                je_doc.flags.skip_inter_branch_injection = True
                je_doc.cancel()
        except Exception:
            frappe.log_error(
                title="IBST companion JE cancel failed",
                message=frappe.get_traceback(),
            )
            raise

    def _cancel_linked_delivery_note(self):
        if not self.delivery_note:
            return
        try:
            dn = frappe.get_doc("Delivery Note", self.delivery_note)
            if dn.docstatus == 1:
                dn.flags.ignore_permissions = True
                dn.cancel()
        except Exception:
            frappe.log_error(title="IBST Delivery Note cancel failed", message=frappe.get_traceback())
            raise

    def _cancel_linked_stock_entry(self):
        if not self.stock_entry:
            return
        try:
            se = frappe.get_doc("Stock Entry", self.stock_entry)
            if se.docstatus == 1:
                se.flags.ignore_permissions = True
                se.cancel()
        except Exception:
            frappe.log_error(title="IBST Stock Entry cancel failed", message=frappe.get_traceback())
            raise


# ------------------------------------------------------------------
# Whitelisted helpers
# ------------------------------------------------------------------

@frappe.whitelist()
def create_delivery_note(ibst_name: str) -> str:
    """Create a Delivery Note from a submitted IBST that has a customer set.

    Called from the 'Create Delivery Note' button when the DN was not created
    on submit (e.g. customer added after the fact via amendment).
    """
    doc = frappe.get_doc("Inter Branch Stock Transfer", ibst_name)
    if doc.docstatus != 1:
        frappe.throw(_("Delivery Note can only be created from a submitted document."))
    if not doc.customer:
        frappe.throw(_("Please set a Customer before creating a Delivery Note."))
    if doc.delivery_note and frappe.db.get_value("Delivery Note", doc.delivery_note, "docstatus") == 1:
        frappe.throw(_("A Delivery Note {0} already exists for this document.").format(doc.delivery_note))
    doc._create_delivery_note()
    return doc.delivery_note


@frappe.whitelist()
def make_journal_entry(ibst_name: str) -> str:
    """Create and submit the inter-branch companion JE for a submitted IBST.

    Returns the new JE name. If a JE already exists for this IBST it is
    returned as-is without creating a duplicate.
    """
    doc = frappe.get_doc("Inter Branch Stock Transfer", ibst_name)
    if doc.docstatus != 1:
        frappe.throw(_("Journal Entry can only be created from a submitted document."))

    # Return existing JE if already created
    existing = frappe.db.sql_list(
        """
        SELECT DISTINCT je.name
        FROM `tabJournal Entry` je
        INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
        WHERE jea.custom_source_doctype = 'Inter Branch Stock Transfer'
          AND jea.custom_source_docname = %s
          AND je.docstatus = 1
        """,
        (ibst_name,),
    )
    if existing:
        return existing[0]

    je_name = doc._create_journal_entry()
    if not je_name:
        frappe.throw(_("Could not create Journal Entry — no transfer value found."))
    return je_name


@frappe.whitelist()
def get_item_valuation_rate(item_code: str, warehouse: str) -> float:
    """Return current valuation rate from Bin, falling back to Item master."""
    rate = flt(
        frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate")
    )
    if not rate:
        rate = flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
    return rate
