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
        if (!frm.doc.is_return) return;
        (frm.doc.items || []).forEach(function (row) {
            if (row.qty > 0) {
                frappe.model.set_value(row.doctype, row.name, "qty", -Math.abs(row.qty));
            }
        });
    },
});

