frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0 || frm.doc.docstatus === 1) {
            frm.add_custom_button(__("New Invoice"), function () {
                window.open("/app/sales-invoice/new", "_blank");
            });
        }
        ensure_update_stock_for_pos_profile(frm);
        set_pos_behavior(frm);
        setup_enter_navigation(frm);
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

        let grid = frm.fields_dict.items.grid;

        grid.wrapper.on('keydown', 'input, select, textarea', function(e) {

            if (e.key !== "Enter") return;

            e.preventDefault();

            let $inputs = $(this).closest('.grid-row')
                                 .find('input, select, textarea')
                                 .filter(':visible');

            let index = $inputs.index(this);

            // 🔹 Same row next column
            if (index < $inputs.length - 1) {
                $inputs.eq(index + 1).focus();
            } 
            // 🔹 Last column → next row
            else {
                let $nextRow = $(this).closest('.grid-row').next('.grid-row');

                if ($nextRow.length) {
                    $nextRow.find('input, select, textarea')
                            .filter(':visible')
                            .first()
                            .focus();
                } else {
                    grid.add_new_row();
                }
            }
        });
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


function setup_enter_navigation(frm) {
    if (!frm.fields_dict.items) return;
    let grid = frm.fields_dict.items.grid;
    if (!grid) return;
    $(document).off("keydown.pos_enter_override");
    $(document).on("keydown.pos_enter_override", function(e) {
        if (e.key !== "Enter") return;
        let $active = $(document.activeElement);
        if (!$active.closest(".grid-row").length) return;
        e.preventDefault();
        e.stopImmediatePropagation();  

        let $currentRow = $active.closest(".grid-row");
        let current_docname = $currentRow.attr("data-name");
        let current_row = grid.get_row(current_docname);

        if (!current_row) return;

        let row_index = grid.grid_rows.indexOf(current_row);

        let $inputs = $currentRow
            .find("input, select, textarea")
            .filter(":visible:not([readonly]):not([disabled])");

        let index = $inputs.index(document.activeElement);
        if (index < $inputs.length - 1) {
            $inputs.eq(index + 1).focus().select();
            return;
        }
        if (row_index < grid.grid_rows.length - 1) {

            let next_row = grid.grid_rows[row_index + 1];
            next_row.activate();

            setTimeout(() => {
                let $nextInputs = $(next_row.row)
                    .find("input, select, textarea")
                    .filter(":visible:not([readonly]):not([disabled])");

                if ($nextInputs.length) {
                    $nextInputs.eq(0).focus().select();
                }
            }, 100);

        } else {

            grid.add_new_row();

            setTimeout(() => {
                let rows = grid.grid_rows;
                let new_row = rows[rows.length - 1];

                if (!new_row) return;

                new_row.activate();

                let $newInputs = $(new_row.row)
                    .find("input, select, textarea")
                    .filter(":visible:not([readonly]):not([disabled])");

                if ($newInputs.length) {
                    $newInputs.eq(0).focus().select();
                }

            }, 150);
        }

    });
}