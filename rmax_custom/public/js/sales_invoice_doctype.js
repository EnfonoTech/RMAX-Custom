/**
 * RMAX Custom: Sales Invoice Form
 *
 * 1. Auto-negate qty for Credit Notes (is_return = 1).
 * 2. Restrict the 'Update Stock' flag: default off, editable only by
 *    Sales Manager / Sales Master Manager / System Manager / Administrator.
 */

const RMAX_UPDATE_STOCK_ROLES = [
    "Sales Manager",
    "Sales Master Manager",
    "System Manager",
];

function _rmax_can_toggle_update_stock() {
    if (frappe.session.user === "Administrator") return true;
    const roles = frappe.user_roles || [];
    return RMAX_UPDATE_STOCK_ROLES.some((r) => roles.includes(r));
}

frappe.ui.form.on("Sales Invoice", {
    onload: function (frm) {
        if (frm.is_new() && !_rmax_can_toggle_update_stock()) {
            // Default off for Branch / Stock / Sales User
            frm.set_value("update_stock", 0);
        }
    },
    refresh: function (frm) {
        const allowed = _rmax_can_toggle_update_stock();
        frm.set_df_property("update_stock", "read_only", allowed ? 0 : 1);
        if (!allowed) {
            frm.set_df_property(
                "update_stock",
                "description",
                "Only Sales Manager or above can enable Update Stock."
            );
        }
    },
    before_save: function (frm) {
        if (!_rmax_can_toggle_update_stock() && frm.doc.update_stock) {
            // Force-off for unauthorised users before server validation runs
            frm.doc.update_stock = 0;
        }

        if (!frm.doc.is_return) return;
        (frm.doc.items || []).forEach(function (row) {
            if (row.qty > 0) {
                frappe.model.set_value(row.doctype, row.name, "qty", -Math.abs(row.qty));
            }
        });
    },
});
