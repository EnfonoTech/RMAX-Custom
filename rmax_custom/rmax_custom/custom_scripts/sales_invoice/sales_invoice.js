frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0 || frm.doc.docstatus === 1) {
            frm.add_custom_button(__("New Invoice"), function () {
                window.open("/app/sales-invoice/new", "_blank");
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
    },
    onload(frm) {
        let grid = frm.fields_dict.items.grid;
        grid.wrapper.off('keydown.enter_nav');
        grid.wrapper.on('keydown.enter_nav', 'input, select, textarea', function(e) {
            if (e.key !== "Enter") return;
            e.preventDefault();
            let $currentRow = $(this).closest('.grid-row');
            let current_docname = $currentRow.attr('data-name');
            let current_row = grid.get_row(current_docname);
            if (!current_row) return;
            let row_index = grid.grid_rows.indexOf(current_row);
            let $inputs = $currentRow
                .find('input, select, textarea')
                .filter(':visible:not([readonly]):not([disabled])');

            let index = $inputs.index(this);
            if (index < $inputs.length - 1) {
                $inputs.eq(index + 1).focus();
            }
            else {
                if (row_index < grid.grid_rows.length - 1) {

                    let next_row = grid.grid_rows[row_index + 1];
                    next_row.activate();

                    setTimeout(() => {
                        let $nextInputs = $(next_row.row)
                            .find('input, select, textarea')
                            .filter(':visible:not([readonly]):not([disabled])');

                        if ($nextInputs.length) {
                            $nextInputs.eq(0).focus(); 
                        }
                    }, 50);

                } else {
                    grid.add_new_row();

                    setTimeout(() => {
                        let new_row = grid.grid_rows[grid.grid_rows.length - 1];

                        if (new_row) {
                            new_row.activate();

                            let $newInputs = $(new_row.row)
                                .find('input, select, textarea')
                                .filter(':visible:not([readonly]):not([disabled])');

                            if ($newInputs.length) {
                                $newInputs.eq(0).focus();
                            }
                        }
                    }, 100);
                }
            }
        });
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


function add_create_customer_button(frm) {

    if (frm.doc.docstatus !== 0) return;
    if (!frm.fields_dict.customer) return;

    const $field = frm.fields_dict.customer.$wrapper;
    const $parent = $field.parent();

    if ($parent.find(".create-customer-btn").length) return;

    const $btn = $(`
        <button type="button"
            class="btn btn-sm btn-secondary create-customer-btn"
            style="margin-bottom: 5px;">
            <i class="fa fa-plus"></i> Create New Customer
        </button>
    `);

    $btn.on("click", function () {
        open_create_customer_dialog(frm);
    });

    $field.before($btn);
}


function open_create_customer_dialog(frm) {

    let company = frm.doc.company || frappe.defaults.get_default("company");

    frappe.db.get_value("Company", company,
        ["country", "default_currency"], function(r) {

        let country = r.country;
        let default_currency = r.default_currency;

        let d = new frappe.ui.Dialog({
            title: "Create New Customer",
            fields: [
                {
                    fieldname: "customer_name",
                    fieldtype: "Data",
                    label: "Customer Name",
                    reqd: 1
                },
                {
                    fieldname: "mobile_no",
                    fieldtype: "Data",
                    label: "Mobile No",
                    reqd: 1
                },
                {
                    fieldname: "email_id",
                    fieldtype: "Data",
                    label: "Email ID"
                },
                { fieldtype: "Section Break", label: "Address Details" },
                {
                    fieldname: "address_type",
                    fieldtype: "Select",
                    label: "Address Type",
                    options: "Billing\nShipping",
                    default: "Billing",
                    reqd: 1
                },
                {
                    fieldname: "address_line1",
                    fieldtype: "Data",
                    label: "Address Line 1",
                    reqd: 1
                },
                {
                    fieldname: "address_line2",
                    fieldtype: "Data",
                    label: "Address Line 2"
                },
                {
                    fieldname: "city",
                    fieldtype: "Data",
                    label: "City/Town",
                    reqd: 1
                },
                {
                    fieldname: "country",
                    fieldtype: "Link",
                    options: "Country",
                    label: "Country",
                    default: country,
                    reqd: 1
                },


            ],
            primary_action_label: "Create Customer",
            primary_action(values) {

                frappe.call({
                    method: "rmax_custom.rmax_custom.custom_scripts.sales_invoice.sales_invoice.create_customer_with_primary_address",
                    args: {
                        customer_name: values.customer_name,
                        mobile_no: values.mobile_no,
                        email_id: values.email_id || null,
                        address_type: values.address_type, 
                        address_line1: values.address_line1,
                        address_line2: values.address_line2 || null,
                        city: values.city,  
                        country: country,
                        default_currency: default_currency
                    },
                    callback: function(r) {
                        if (r.message) {

                            frm.set_value("customer", r.message.customer);
                            frm.refresh_field("customer");

                            frappe.show_alert({
                                message: r.message.message,
                                indicator: "green"
                            });

                            d.hide();
                        }
                    }
                });
            }
        });

        d.show();
    });
}


