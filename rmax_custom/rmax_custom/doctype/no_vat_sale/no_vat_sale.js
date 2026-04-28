/**
 * RMAX Custom: No VAT Sale form.
 *  - Auto-fetches selling rate + valuation rate on item pick.
 *  - Filters Warehouse dropdown by the selected Branch's Branch
 *    Configuration → Warehouse rows.
 *  - Adds Submit-for-Approval / Approve / Reject buttons driven by
 *    `approval_status`. Only the named approver (or Sales/System Mgr)
 *    sees Approve/Reject.
 */

const _RMAX_NVS_OVERRIDE_ROLES = ["Sales Manager", "System Manager"];

frappe.ui.form.on("No VAT Sale", {
    onload: function (frm) {
        _rmax_setup_warehouse_query(frm);
    },
    refresh: function (frm) {
        _rmax_setup_warehouse_query(frm);
        _rmax_add_ledger_buttons(frm);
        _rmax_add_approval_buttons(frm);
        _rmax_render_status_indicator(frm);
    },
    branch: function (frm) {
        // Branch changed — refresh permitted warehouses and clear stale pick.
        if (frm.doc.warehouse) {
            frappe.call({
                method: "rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_branch_warehouses",
                args: { branch: frm.doc.branch },
                callback: function (r) {
                    const allowed = (r.message || []);
                    if (frm.doc.warehouse && !allowed.includes(frm.doc.warehouse)) {
                        frm.set_value("warehouse", null);
                    }
                },
            });
        }
        _rmax_setup_warehouse_query(frm);
    },
    company: function (frm) {
        _rmax_prefill_accounts(frm);
    },
    mode_of_payment: function (frm) {
        _rmax_prefill_accounts(frm);
    },
});

function _rmax_render_status_indicator(frm) {
    if (frm.doc.docstatus === 1) return;
    const map = {
        "Draft": ["Draft", "grey"],
        "Pending Approval": ["Pending Approval", "orange"],
        "Approved": ["Approved", "green"],
        "Rejected": ["Rejected", "red"],
    };
    const entry = map[frm.doc.approval_status] || map["Draft"];
    frm.page.set_indicator(entry[0], entry[1]);
}

function _rmax_can_act_as_approver(frm) {
    const user = frappe.session.user;
    if (user === "Administrator") return true;
    if (frm.doc.approved_by && user === frm.doc.approved_by) return true;
    return (frappe.user_roles || []).some((r) =>
        _RMAX_NVS_OVERRIDE_ROLES.includes(r)
    );
}

function _rmax_add_approval_buttons(frm) {
    if (frm.is_new()) return;
    if (frm.doc.docstatus !== 0) return;

    const status = frm.doc.approval_status || "Draft";

    // Send for Approval — visible to creator while still Draft / Rejected
    if (status === "Draft" || status === "Rejected") {
        frm.add_custom_button(
            __("Send for Approval"),
            function () {
                if (frm.is_dirty()) {
                    frappe.msgprint(__("Save changes first."));
                    return;
                }
                if (!frm.doc.approved_by) {
                    frappe.msgprint(__("Pick an Approver first."));
                    return;
                }
                frappe.call({
                    method: "rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.submit_for_approval",
                    args: { name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Sending for approval..."),
                    callback: function () {
                        frm.reload_doc();
                        frappe.show_alert({
                            message: __("Sent for approval"),
                            indicator: "green",
                        });
                    },
                });
            },
            __("Approval")
        );
    }

    // Approve / Reject — only for the named approver while Pending Approval
    if (status === "Pending Approval" && _rmax_can_act_as_approver(frm)) {
        frm.add_custom_button(
            __("Approve & Submit"),
            function () {
                _rmax_approve_with_remarks(frm);
            },
            __("Approval")
        );
        frm.add_custom_button(
            __("Reject"),
            function () {
                _rmax_reject_with_remarks(frm);
            },
            __("Approval")
        );
    }
}

function _rmax_approve_with_remarks(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Approve No VAT Sale"),
        fields: [
            {
                fieldname: "remarks",
                fieldtype: "Small Text",
                label: __("Approval Remarks"),
            },
        ],
        primary_action_label: __("Approve & Submit"),
        primary_action(values) {
            d.hide();
            frappe.call({
                method: "rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.approve_no_vat_sale",
                args: { name: frm.doc.name, remarks: values.remarks || null },
                freeze: true,
                freeze_message: __("Approving..."),
                callback: function () {
                    frm.reload_doc();
                    frappe.show_alert({
                        message: __("Approved & submitted"),
                        indicator: "green",
                    });
                },
            });
        },
    });
    d.show();
}

function _rmax_reject_with_remarks(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Reject No VAT Sale"),
        fields: [
            {
                fieldname: "remarks",
                fieldtype: "Small Text",
                label: __("Reason"),
                reqd: 1,
            },
        ],
        primary_action_label: __("Reject"),
        primary_action(values) {
            d.hide();
            frappe.call({
                method: "rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.reject_no_vat_sale",
                args: { name: frm.doc.name, remarks: values.remarks },
                freeze: true,
                freeze_message: __("Rejecting..."),
                callback: function () {
                    frm.reload_doc();
                    frappe.show_alert({
                        message: __("Rejected"),
                        indicator: "red",
                    });
                },
            });
        },
    });
    d.show();
}

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

        // Branch-scoped: pull permitted warehouses from Branch Configuration.
        // Falls back to the company-only filter if no branch picked yet.
        if (frm.doc.branch) {
            return new Promise(function (resolve) {
                frappe.call({
                    method:
                        "rmax_custom.rmax_custom.doctype.no_vat_sale.no_vat_sale.get_branch_warehouses",
                    args: { branch: frm.doc.branch },
                    callback: function (r) {
                        const allowed = (r.message || []);
                        if (allowed.length) {
                            filters.name = ["in", allowed];
                        }
                        resolve({
                            filters: filters,
                            ignore_user_permissions: 1,
                        });
                    },
                });
            });
        }

        return { filters: filters, ignore_user_permissions: 1 };
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
