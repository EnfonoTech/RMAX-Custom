// Copyright (c) 2026, Enfono and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Transfer', {

    onload: function(frm) {
        if (frm.is_new()) {
            set_default_target(frm);
        }
        frm.set_query('set_source_warehouse', function() {
            return {
                ignore_user_permissions: 1,
                 filters: {
                    name: frm.doc.set_source_warehouse
                }
            };
        });
        frm.set_query('set_target_warehouse', function() {
            return {
                ignore_user_permissions: 1,
                filters: {
                    company: frm.doc.company,
                    name: ["!=", frm.doc.set_source_warehouse]  

                }
            };
        });
    },
    refresh: function(frm) {
        if (frm.doc.__islocal && !frm.doc.__source_fixed) {
            setTimeout(() => {
                frm.set_value('set_target_warehouse', '');
                frm.doc.__source_fixed = true;

            }, 200);
        }
    },
    before_save: function(frm) {

    if (frm.doc.set_target_warehouse) {

        frappe.call({
            method: "frappe.client.get_list",
            async: false,
            args: {
                doctype: "User Permission",
                filters: {
                    user: frappe.session.user,
                    allow: "Warehouse",
                    for_value: frm.doc.set_target_warehouse
                },
                fields: ["name"]
            },
            callback: function(r) {

                if (!r.message.length) {

                    frappe.call({
                        method: "frappe.client.insert",
                        async: false,
                        args: {
                            doc: {
                                doctype: "User Permission",
                                user: frappe.session.user,
                                allow: "Warehouse",
                                for_value: frm.doc.set_target_warehouse
                            }
                        }
                    });

                }
            }
        });
    }
}

});

function set_default_target(frm) {

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "User Permission",
            filters: {
                user: frappe.session.user,
                allow: "Warehouse",
                is_default: 1
            },
            fields: ["for_value"],
            limit: 1
        },
        callback: function(r) {

            if (r.message && r.message.length > 0) {
                let default_wh = r.message[0].for_value;
                if (!frm.doc.set_source_warehouse) {
                    frm.set_value('set_source_warehouse', default_wh);
                }
            }
        }
    });
}

frappe.ui.form.on('Stock Transfer Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.item_code) return;
        frappe.db.get_value("Item", row.item_code, "stock_uom", (r) => {
            if (r && r.stock_uom) {
                frappe.model.set_value(cdt, cdn, "uom", r.stock_uom);
                trigger_conversion(frm, cdt, cdn);
            }
        });
        set_uom_query(frm, cdt, cdn);
    },
    uom: function(frm, cdt, cdn) {
        trigger_conversion(frm, cdt, cdn);
    }
});


function set_uom_query(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row.item_code) return;
    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Item",
            name: row.item_code
        },
        callback: function(r) {
            if (r.message && r.message.uoms) {
                let uom_list = r.message.uoms.map(d => d.uom);
                frm.fields_dict["items"].grid.get_field("uom").get_query = function(doc, cdt, cdn) {
                    return {
                        filters: {
                            name: ["in", uom_list]   
                        }
                    };
                };

            }
        }
    });
}


function trigger_conversion(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!(row.item_code && row.uom)) return;
    frappe.call({
        method: "rmax_custom.rmax_custom.doctype.stock_transfer.stock_transfer.get_item_uom_conversion",
        args: {
            item_code: row.item_code,
            uom: row.uom
        },
        callback: function(r) {
            if (r.message !== undefined) {
                frappe.model.set_value(
                    cdt,
                    cdn,
                    "uom_conversion_factor",
                    r.message
                );
            }
        }
    });
}