/**
 * RMAX Custom: No VAT Sale form.
 * Auto-fetches selling rate + valuation rate on item pick.
 */

frappe.ui.form.on("No VAT Sale", {
    onload: function (frm) {
        _rmax_setup_warehouse_query(frm);
    },
    refresh: function (frm) {
        _rmax_setup_warehouse_query(frm);
        _rmax_add_ledger_buttons(frm);
    },
    company: function (frm) {
        _rmax_prefill_accounts(frm);
    },
    mode_of_payment: function (frm) {
        _rmax_prefill_accounts(frm);
    },
});

function _rmax_add_ledger_buttons(frm) {
    if (frm.doc.docstatus !== 1) return;

    if (frm.doc.stock_entry) {
        frm.add_custom_button(
            __("Accounting Ledger"),
            function () {
                frappe.route_options = {
                    company: frm.doc.company,
                    from_date: frm.doc.posting_date,
                    to_date: frm.doc.posting_date,
                    voucher_type: "Stock Entry",
                    voucher_no: frm.doc.stock_entry,
                    group_by: "Group by Voucher (Consolidated)",
                };
                frappe.set_route("query-report", "General Ledger");
            },
            __("View")
        );

        frm.add_custom_button(
            __("Stock Ledger"),
            function () {
                frappe.route_options = {
                    company: frm.doc.company,
                    from_date: frm.doc.posting_date,
                    to_date: frm.doc.posting_date,
                    voucher_type: "Stock Entry",
                    voucher_no: frm.doc.stock_entry,
                };
                frappe.set_route("query-report", "Stock Ledger");
            },
            __("View")
        );
    }

    if (frm.doc.journal_entry) {
        frm.add_custom_button(
            __("Accounting Ledger (Cash)"),
            function () {
                frappe.route_options = {
                    company: frm.doc.company,
                    from_date: frm.doc.posting_date,
                    to_date: frm.doc.posting_date,
                    voucher_type: "Journal Entry",
                    voucher_no: frm.doc.journal_entry,
                    group_by: "Group by Voucher (Consolidated)",
                };
                frappe.set_route("query-report", "General Ledger");
            },
            __("View")
        );
    }

    if (frm.doc.journal_entry) {
        frm.add_custom_button(
            __("Journal Entry"),
            function () {
                frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry);
            },
            __("View")
        );
    }

    if (frm.doc.stock_entry) {
        frm.add_custom_button(
            __("Stock Entry"),
            function () {
                frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
            },
            __("View")
        );
    }
}

function _rmax_prefill_accounts(frm) {
    if (!frm.doc.company) return;
    frappe.call({
        method: "rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_default_accounts",
        args: {
            company: frm.doc.company,
            mode_of_payment: frm.doc.mode_of_payment || null,
        },
        callback: function (r) {
            if (!r.message) return;
            if (r.message.naseef_account) {
                frm.set_value("naseef_account", r.message.naseef_account);
            }
            if (r.message.cogs_account) {
                frm.set_value("cogs_account", r.message.cogs_account);
            }
            if (r.message.cash_account) {
                frm.set_value("cash_account", r.message.cash_account);
            }
        },
    });
}

function _rmax_setup_warehouse_query(frm) {
    frm.set_query("warehouse", function () {
        const filters = { is_group: 0 };
        if (frm.doc.company) filters.company = frm.doc.company;
        return { filters: filters };
    });
}

frappe.ui.form.on("No VAT Sale Item", {
    item_code: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code) return;

        // Selling rate from No VAT Price list
        frappe.call({
            method: "rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_item_rate",
            args: { item_code: row.item_code },
            callback: function (r) {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, "rate", r.message);
                }
            },
        });

        // Valuation rate from Bin
        if (frm.doc.warehouse) {
            frappe.call({
                method: "rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_item_valuation",
                args: { item_code: row.item_code, warehouse: frm.doc.warehouse },
                callback: function (r) {
                    frappe.model.set_value(cdt, cdn, "valuation_rate", r.message || 0);
                },
            });
        }
    },
    qty: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row.amount = (row.rate || 0) * (row.qty || 0);
        row.cost_amount = (row.valuation_rate || 0) * (row.qty || 0);
        frm.refresh_field("items");
    },
    rate: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row.amount = (row.rate || 0) * (row.qty || 0);
        frm.refresh_field("items");
    },
});
