frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0 || frm.doc.docstatus === 1) {
            frm.add_custom_button(__("New Invoice"), function () {
                window.open("/app/sales-invoice/new", "_blank");
            });
        }
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Return Invoice'), function() {
                frappe.call({
                    method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_sales_return",
                    args: {
                        source_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.model.sync(r.message);
                            frappe.set_route("Form", r.message.doctype, r.message.name);
                        }
                    }
                });

            });
        }
        set_pos_behavior(frm);
    },
    custom_payment_mode(frm) {
        set_pos_behavior(frm);
        set_customer_filter(frm);
    },
    onload(frm) {
        set_customer_filter(frm);
    },
    before_save(frm) {
        if (frm.doc.docstatus !== 0) return;
        if (frm.is_new()) return;
        if (frm._submit_checked) return;
        frappe.validated = false;
        frappe.confirm(
            "Do you want to Submit this Sales Invoice now?",
            
            function () {
                frm._submit_checked = true;
                frm.save('Submit');
            },
            
            function () {
                frm._submit_checked = true;
                frm.save();
            }
        );
    },
    items_add: function(frm) {
        check_stock(frm);
    }

});


function set_pos_behavior(frm) {
    if (!frm.doc.custom_payment_mode) return;
    if (frm.doc.custom_payment_mode === "Cash") {
        frm.set_value("is_pos", 1);
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