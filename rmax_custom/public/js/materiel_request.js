frappe.ui.form.on('Material Request', {
    refresh: function(frm) {
        if (frm.is_new()) {
            set_default_target(frm);
        }
        frm.set_query('set_warehouse', function() {
            return {
                ignore_user_permissions: 1,
                 filters: {
                    name: frm.doc.set_warehouse
                }
            };
        });
        frm.set_query('set_from_warehouse', function() {
            return {
                ignore_user_permissions: 1,
                filters: {
                    company: frm.doc.company,
                    name: ["!=", frm.doc.set_warehouse]  

                }
            };
        })

    },
    material_request_type: function(frm) {
        set_default_target(frm);
    },
});

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

