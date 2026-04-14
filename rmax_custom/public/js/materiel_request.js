frappe.ui.form.on('Material Request', {
    refresh: function(frm) {
        if (frm.is_new()) {
            set_default_target(frm);
        }
        _setup_warehouse_queries(frm);

        // Hide standard ERPNext buttons and add Stock Transfer button
        if (frm.doc.docstatus === 1 && frm.doc.material_request_type === "Material Transfer") {
            // Wait for ERPNext buttons to render, then remove them
            setTimeout(function() {
                _hide_standard_transfer_buttons(frm);
                _add_stock_transfer_button(frm);
            }, 500);
        }
    },
    material_request_type: function(frm) {
        set_default_target(frm);
    },
});

/**
 * Hide standard ERPNext "Material Transfer", "Material Transfer (In Transit)",
 * and "Pick List" buttons from the Create menu.
 */
function _hide_standard_transfer_buttons(frm) {
    var buttons_to_hide = [
        "Material Transfer",
        "Material Transfer (In Transit)",
        "Pick List"
    ];

    buttons_to_hide.forEach(function(label) {
        // Remove from inner_toolbar (Create group)
        frm.page.inner_toolbar
            .find('.btn-default:contains("' + label + '")')
            .closest('.btn-group, .inner-group-button')
            .find('.dropdown-menu a:contains("' + label + '")')
            .closest('li')
            .hide();

        // Also try direct removal from custom buttons
        var $btn = frm.custom_buttons && frm.custom_buttons[__(label)];
        if ($btn && $btn.length) {
            $btn.hide();
        }
    });

    // Also hide from dropdown menu items
    frm.page.inner_toolbar.find('.dropdown-item, .dropdown-menu a').each(function() {
        var text = $(this).text().trim();
        if (buttons_to_hide.includes(text)) {
            $(this).closest('li').length ? $(this).closest('li').hide() : $(this).hide();
        }
    });
}

/**
 * Add "Stock Transfer" button to create a Stock Transfer from this MR.
 */
function _add_stock_transfer_button(frm) {
    if (frm.doc.status === "Stopped" || frm.doc.per_ordered >= 100) return;

    frm.add_custom_button(__("Stock Transfer"), function() {
        _create_stock_transfer_from_mr(frm);
    }, __("Create"));
}

/**
 * Create a Stock Transfer pre-filled from this Material Request.
 */
function _create_stock_transfer_from_mr(frm) {
    frappe.call({
        method: "rmax_custom.api.material_request.create_stock_transfer_from_mr",
        args: {
            material_request: frm.doc.name
        },
        freeze: true,
        freeze_message: __("Creating Stock Transfer..."),
        callback: function(r) {
            if (r.message) {
                frappe.set_route("Form", "Stock Transfer", r.message);
            }
        }
    });
}

function _setup_warehouse_queries(frm) {
    // Target warehouse: show all user's permitted warehouses
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "User Permission",
            filters: {
                user: frappe.session.user,
                allow: "Warehouse"
            },
            fields: ["for_value"],
            limit_page_length: 0
        },
        async: false,
        callback: function(r) {
            var permitted = (r.message || []).map(function(d) { return d.for_value; });
            frm.set_query('set_warehouse', function() {
                if (permitted.length) {
                    return {
                        ignore_user_permissions: 1,
                        filters: {
                            company: frm.doc.company,
                            is_group: 0,
                            name: ["in", permitted]
                        }
                    };
                }
                return {
                    filters: {
                        company: frm.doc.company,
                        is_group: 0
                    }
                };
            });
        }
    });

    // Source warehouse: ignore user permissions (can request FROM any branch)
    frm.set_query('set_from_warehouse', function() {
        return {
            ignore_user_permissions: 1,
            filters: {
                company: frm.doc.company,
                is_group: 0,
                name: ["!=", frm.doc.set_warehouse]
            }
        };
    });
}

function set_default_target(frm) {
    if (!frm.doc.set_warehouse) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "User Permission",
                filters: {
                    user: frappe.session.user,
                    allow: "Warehouse",
                    is_default: "1"
                },
                fields: ["for_value"]
            },
            callback: function(r) {
                if (r.message && r.message.length > 0 && r.message[0].for_value) {
                    let default_wh = r.message[0].for_value;
                    frm.set_value('set_warehouse', default_wh).then(() => {
                        frm.refresh_field('set_warehouse');
                    });
                }
            }
        });
    }
}
