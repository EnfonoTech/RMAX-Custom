/**
 * RMAX Custom: No VAT Sale form.
 * Auto-fetches selling rate + valuation rate on item pick.
 */

frappe.ui.form.on("No VAT Sale", {
    company: function (frm) {
        frm.trigger("_load_default_accounts");
    },
    mode_of_payment: function (frm) {
        frm.trigger("_load_default_accounts");
    },
    _load_default_accounts: function (frm) {
        if (!frm.doc.company) return;
        frappe.db.get_doc("Company", frm.doc.company).then((c) => {
            if (c.custom_novat_naseef_account) {
                frm.set_value("naseef_account", c.custom_novat_naseef_account);
            }
            if (c.custom_novat_cogs_account) {
                frm.set_value("cogs_account", c.custom_novat_cogs_account);
            }
        });

        if (frm.doc.mode_of_payment) {
            frappe.db
                .get_value(
                    "Mode of Payment Account",
                    {
                        parent: frm.doc.mode_of_payment,
                        company: frm.doc.company,
                    },
                    "default_account"
                )
                .then((r) => {
                    if (r.message && r.message.default_account) {
                        frm.set_value("cash_account", r.message.default_account);
                    }
                });
        }
    },
    branch: function (frm) {
        frm.set_query("warehouse", function () {
            return { filters: { branch: frm.doc.branch, is_group: 0 } };
        });
    },
});

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
