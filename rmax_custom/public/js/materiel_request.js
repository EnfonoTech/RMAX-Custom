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
    // Target warehouse: only user's permitted warehouses (from User Permissions)
    // No ignore_user_permissions — Frappe filters by User Permission automatically
    frm.set_query('set_warehouse', function() {
        return {
            filters: {
                company: frm.doc.company,
                is_group: 0
            }
        };
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
