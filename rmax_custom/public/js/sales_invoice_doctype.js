/**
 * RMAX Custom: Sales Invoice Form
 *
 * 1. New SI defaults: update_stock = 1 and set_warehouse picked from the
 *    user's default Warehouse User Permission so stock movement posts
 *    against the correct warehouse automatically.
 * 2. Branch Users cannot toggle update_stock (read-only). Elevated roles
 *    (Sales Manager, Sales Master Manager, Stock Manager, System Manager)
 *    keep full control.
 * 3. Auto-negate qty on save for Credit Notes (is_return = 1).
 */

const RMAX_UPDATE_STOCK_ELEVATED_ROLES = [
    "Sales Manager",
    "Sales Master Manager",
    "Stock Manager",
    "System Manager",
];

function _rmax_is_locked_branch_user() {
    if (frappe.session.user === "Administrator") return false;
    const roles = frappe.user_roles || [];
    if (!roles.includes("Branch User")) return false;
    return !RMAX_UPDATE_STOCK_ELEVATED_ROLES.some((r) => roles.includes(r));
}

function _rmax_fetch_default_warehouse(callback) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "User Permission",
            filters: {
                user: frappe.session.user,
                allow: "Warehouse",
                is_default: 1,
            },
            fields: ["for_value"],
            limit_page_length: 1,
        },
        callback: function (r) {
            const wh =
                (r.message && r.message.length && r.message[0].for_value) || null;
            callback(wh);
        },
    });
}

frappe.ui.form.on("Sales Invoice", {
    onload: function (frm) {
        if (!frm.is_new()) return;

        if (!frm.doc.update_stock) {
            frm.set_value("update_stock", 1);
        }

        if (!frm.doc.set_warehouse) {
            _rmax_fetch_default_warehouse(function (wh) {
                if (wh && frm.is_new() && !frm.doc.set_warehouse) {
                    frm.set_value("set_warehouse", wh);
                }
            });
        }
    },
    refresh: function (frm) {
        if (_rmax_is_locked_branch_user()) {
            frm.set_df_property("update_stock", "read_only", 1);
            frm.set_df_property(
                "update_stock",
                "description",
                "Locked for Branch Users. Contact a Sales Manager to change."
            );
        }
    },
    before_save: function (frm) {
        _rmax_apply_branch_payment_accounts(frm);

        if (!frm.doc.is_return) return;
        (frm.doc.items || []).forEach(function (row) {
            if (row.qty > 0) {
                frappe.model.set_value(row.doctype, row.name, "qty", -Math.abs(row.qty));
            }
        });
    },
});

frappe.ui.form.on("Sales Invoice Payment", {
    mode_of_payment: function (frm, cdt, cdn) {
        _rmax_apply_branch_payment_accounts(frm, cdt, cdn);
    },
});

let _rmax_branch_accounts_cache = null;

function _rmax_get_branch_accounts(callback) {
    if (_rmax_branch_accounts_cache) {
        callback(_rmax_branch_accounts_cache);
        return;
    }
    frappe.call({
        method: "rmax_custom.branch_defaults.get_user_branch_accounts",
        args: {},
        callback: function (r) {
            _rmax_branch_accounts_cache = r.message || {};
            callback(_rmax_branch_accounts_cache);
        },
    });
}

function _rmax_apply_branch_payment_accounts(frm, cdt, cdn) {
    // Skip elevated roles — server hook also bypasses them.
    const roles = frappe.user_roles || [];
    const elevated = ["System Manager", "Sales Manager", "Sales Master Manager", "Stock Manager"];
    if (elevated.some((r) => roles.includes(r))) return;
    if (!roles.includes("Branch User")) return;

    const payments = frm.doc.payments || [];
    if (!payments.length) return;

    _rmax_get_branch_accounts(function (accts) {
        if (!accts || (!accts.cash_mop && !accts.bank_mop)) return;

        // Cache MoP type lookups per session.
        const mops = [...new Set(payments.map((p) => p.mode_of_payment).filter(Boolean))];
        if (!mops.length) return;

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Mode of Payment",
                filters: { name: ["in", mops] },
                fields: ["name", "type"],
                limit_page_length: 100,
            },
            callback: function (r) {
                const type_map = {};
                (r.message || []).forEach((m) => {
                    type_map[m.name] = m.type;
                });

                payments.forEach(function (row) {
                    if (cdn && row.name !== cdn) return;
                    if (!row.mode_of_payment) return;
                    const t = type_map[row.mode_of_payment];

                    let target_mop = null;
                    let target_account = null;
                    if (t === "Cash" && accts.cash_mop) {
                        target_mop = accts.cash_mop;
                        target_account = accts.cash_account;
                    } else if (t === "Bank" && accts.bank_mop) {
                        target_mop = accts.bank_mop;
                        target_account = accts.bank_account;
                    }
                    if (!target_mop) return;

                    if (row.mode_of_payment !== target_mop) {
                        frappe.model.set_value(row.doctype, row.name, "mode_of_payment", target_mop);
                    }
                    if (target_account) {
                        frappe.model.set_value(row.doctype, row.name, "account", target_account);
                    }
                });
            },
        });
    });
}

