frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0 || frm.doc.docstatus === 1) {
            frm.add_custom_button(__("New Invoice"), function () {
                window.open("/app/sales-invoice/new", "_blank");
            });
        }
        ensure_update_stock_for_pos_profile(frm);
        set_pos_behavior(frm);
    },
    pos_profile(frm) {
        ensure_update_stock_for_pos_profile(frm);
    },
    update_stock(frm) {
        // Keep update_stock checked when POS Profile is selected.
        ensure_update_stock_for_pos_profile(frm);
    },
    custom_payment_mode(frm) {
        set_pos_behavior(frm);
        set_customer_filter(frm);
    },
    onload(frm) {
        set_customer_filter(frm);
    },
    items_add: function(frm) {
        check_stock(frm);
    },
    onload(frm) {
        // Enter key navigation is now handled globally by enter_navigation_global.js
    }
});

function ensure_update_stock_for_pos_profile(frm) {
    if (!frm || !frm.doc) return;
    if (frm.doc.pos_profile && !frm.doc.update_stock) {
        frm.set_value("update_stock", 1);
    }
}


function set_pos_behavior(frm) {
    if (!frm.doc.custom_payment_mode) return;
    if (frm.doc.custom_payment_mode === "Cash") {
        // Do not auto-enable POS / Include Payment when selecting Cash
        // (user wants Payment Entry method via popup, not Sales Invoice payments table)
    }
    else if (frm.doc.custom_payment_mode === "Credit") {
        frm.set_value("is_pos", 0);
    }
}


function set_customer_filter(frm) {
    if (frm.doc.custom_payment_mode === 'Credit') {
        frm.set_query('customer', function () {
            return {
                filters: [
                    ["Customer Credit Limit", "credit_limit", ">", 0]
                ]
            };
        });
    } else {
        frm.set_query('customer', function () {
            return {};
        });
    }
}

frappe.ui.form.on("Sales Invoice Item", {
    items_add: function(frm, cdt, cdn) {
        check_stock(frm, cdt, cdn);  
    },
    item_code: function(frm, cdt, cdn) {
        check_stock(frm, cdt, cdn);
    },
    qty: function(frm, cdt, cdn) {
        check_stock(frm, cdt, cdn);
    }
});

function check_stock(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row || !row.item_code || !row.qty || !row.warehouse) return;
    frappe.call({
        method: "erpnext.stock.utils.get_stock_balance",
        args: {
            item_code: row.item_code,
            warehouse: row.warehouse
        },
        callback: function(r) {
            let stock = r.message || 0;
            if (row.qty > stock) {
                frappe.msgprint({
                    title: "Stock Alert",
                    message: `Only ${stock} item${stock > 1 ? 's' : ''} are currently available in ${row.warehouse}.`,
                    indicator: "red"
                });

                frappe.model.set_value(cdt, cdn, "qty", stock);
            }
        }
    });
}


// Enter navigation is now handled globally by enter_navigation_global.js