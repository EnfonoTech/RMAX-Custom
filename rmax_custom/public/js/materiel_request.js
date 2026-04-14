/**
 * RMAX Custom: Material Request — warehouse defaults and queries.
 * Loaded via app_include_js (bundled).
 *
 * Button logic (hide/add) is in material_request_doctype.js (doctype_js hook).
 */

frappe.ui.form.on('Material Request', {
    refresh: function(frm) {
        if (frm.is_new()) {
            set_default_target(frm);
        }
        _setup_warehouse_queries(frm);
    },
    material_request_type: function(frm) {
        set_default_target(frm);
    },
});

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
