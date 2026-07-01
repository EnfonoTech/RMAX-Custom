// Copyright (c) 2026, Enfono and contributors
// For license information, please see license.txt

frappe.ui.form.on('Inter Branch Stock Transfer', {

    onload: function (frm) {
        _setup_warehouse_queries(frm);
        _setup_price_list_query(frm);
        if (frm.is_new()) {
            _set_default_source_warehouse(frm);
        }
    },

    refresh: function (frm) {
        _setup_warehouse_queries(frm);
        _setup_price_list_query(frm);
        _setup_buttons(frm);
        _toggle_posting_time(frm);
    },

    set_posting_time: function (frm) {
        _toggle_posting_time(frm);
    },

    company: function (frm) {
        _setup_warehouse_queries(frm);
    },

    from_warehouse: function (frm) {
        (frm.doc.items || []).forEach(function (item) {
            if (!item.s_warehouse || item.s_warehouse === frm.doc._prev_from_wh) {
                frappe.model.set_value(item.doctype, item.name, 's_warehouse', frm.doc.from_warehouse);
            }
        });
        frm.doc._prev_from_wh = frm.doc.from_warehouse;
        _fetch_valuation_rates_for_all_items(frm);
    },

    to_warehouse: function (frm) {
        (frm.doc.items || []).forEach(function (item) {
            if (!item.t_warehouse || item.t_warehouse === frm.doc._prev_to_wh) {
                frappe.model.set_value(item.doctype, item.name, 't_warehouse', frm.doc.to_warehouse);
            }
        });
        frm.doc._prev_to_wh = frm.doc.to_warehouse;
    },

    customer: function (frm) {
        if (frm.doc.customer) {
            frappe.db.get_value('Customer', frm.doc.customer, 'customer_name', function (r) {
                if (r && r.customer_name) {
                    frm.set_value('customer_name', r.customer_name);
                }
            });
        } else {
            frm.set_value('customer_name', '');
        }
    },

    price_list: function (frm) {
        if (frm.doc.price_list) {
            _fetch_price_list_rates_for_all_items(frm);
        }
    },
});


// ─── Item Handlers ────────────────────────────────────────────────────────────

frappe.ui.form.on('Inter Branch Stock Transfer Item', {

    item_code: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.item_code) return;

        frappe.db.get_value('Item', row.item_code, ['item_name', 'stock_uom', 'description'], function (r) {
            if (!r) return;
            frappe.model.set_value(cdt, cdn, 'item_name', r.item_name);
            frappe.model.set_value(cdt, cdn, 'stock_uom', r.stock_uom);
            frappe.model.set_value(cdt, cdn, 'uom', r.stock_uom);
            frappe.model.set_value(cdt, cdn, 'conversion_factor', 1);
            if (!row.description && r.description) {
                frappe.model.set_value(cdt, cdn, 'description', r.description);
            }
            _set_uom_query(frm, cdt, cdn);
        });

        if (frm.doc.from_warehouse && !row.s_warehouse) {
            frappe.model.set_value(cdt, cdn, 's_warehouse', frm.doc.from_warehouse);
        }
        if (frm.doc.to_warehouse && !row.t_warehouse) {
            frappe.model.set_value(cdt, cdn, 't_warehouse', frm.doc.to_warehouse);
        }

        _fetch_valuation_rate(frm, cdt, cdn);
    },

    s_warehouse: function (frm, cdt, cdn) {
        _fetch_valuation_rate(frm, cdt, cdn);
    },

    uom: function (_frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.item_code || !row.uom) return;
        frappe.call({
            method: 'rmax_custom.rmax_custom.doctype.stock_transfer.stock_transfer.get_item_uom_conversion',
            args: { item_code: row.item_code, uom: row.uom },
            callback: function (r) {
                if (r.message !== undefined) {
                    frappe.model.set_value(cdt, cdn, 'conversion_factor', r.message);
                    frappe.model.set_value(cdt, cdn, 'transfer_qty', flt(locals[cdt][cdn].qty) * flt(r.message));
                }
            }
        });
    },

    qty: function (_frm, cdt, cdn) {
        _recalculate_row_amount(cdt, cdn);
    },

    basic_rate: function (_frm, cdt, cdn) {
        _recalculate_row_amount(cdt, cdn);
    },
});


// ─── Helpers ──────────────────────────────────────────────────────────────────

function _toggle_posting_time(frm) {
    frm.set_df_property('posting_time', 'read_only', frm.doc.set_posting_time ? 0 : 1);
    frm.set_df_property('posting_date', 'read_only', frm.doc.set_posting_time ? 0 : 1);
}

function _setup_buttons(frm) {
    frm.remove_custom_button(__('Create Delivery Note'));

    if (frm.doc.docstatus !== 1) return;

    // Delivery Note button
    if (frm.doc.customer && !frm.doc.delivery_note) {
        frm.add_custom_button(__('Create Delivery Note'), function () {
            frappe.confirm(
                __('Create a Delivery Note for customer <b>{0}</b>?', [frm.doc.customer]),
                function () {
                    frappe.call({
                        method: 'rmax_custom.rmax_custom.doctype.inter_branch_stock_transfer.inter_branch_stock_transfer.create_delivery_note',
                        args: { ibst_name: frm.doc.name },
                        callback: function (r) {
                            if (r.message) {
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }, __('Create'));
    }
}

function _setup_warehouse_queries(frm) {
    frm.set_query('from_warehouse', function () {
        return { filters: { company: frm.doc.company, is_group: 0 } };
    });
    frm.set_query('to_warehouse', function () {
        return {
            ignore_user_permissions: 1,
            filters: {
                company: frm.doc.company,
                is_group: 0,
                name: ['!=', frm.doc.from_warehouse || '']
            }
        };
    });
    frm.fields_dict['items'].grid.get_field('s_warehouse').get_query = function (doc) {
        return { filters: { company: doc.company, is_group: 0 } };
    };
    frm.fields_dict['items'].grid.get_field('t_warehouse').get_query = function (doc) {
        return { ignore_user_permissions: 1, filters: { company: doc.company, is_group: 0 } };
    };
}

function _set_default_source_warehouse(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'User Permission',
            filters: { user: frappe.session.user, allow: 'Warehouse', is_default: 1 },
            fields: ['for_value'],
            limit: 1
        },
        callback: function (r) {
            if (r.message && r.message.length > 0 && !frm.doc.from_warehouse) {
                frm.set_value('from_warehouse', r.message[0].for_value);
            }
        }
    });
}

function _set_uom_query(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row.item_code) return;
    frappe.call({
        method: 'frappe.client.get',
        args: { doctype: 'Item', name: row.item_code },
        callback: function (r) {
            if (r.message && r.message.uoms) {
                let uom_list = r.message.uoms.map(function (d) { return d.uom; });
                frm.fields_dict['items'].grid.get_field('uom').get_query = function () {
                    return { filters: { name: ['in', uom_list] } };
                };
            }
        }
    });
}

function _fetch_valuation_rate(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row.item_code) return;
    let warehouse = row.s_warehouse || frm.doc.from_warehouse;
    if (!warehouse) return;

    frappe.call({
        method: 'rmax_custom.rmax_custom.doctype.inter_branch_stock_transfer.inter_branch_stock_transfer.get_item_valuation_rate',
        args: { item_code: row.item_code, warehouse: warehouse },
        callback: function (r) {
            if (r.message !== undefined && !flt(locals[cdt][cdn].basic_rate)) {
                frappe.model.set_value(cdt, cdn, 'basic_rate', r.message);
                frappe.model.set_value(cdt, cdn, 'valuation_rate', r.message);
                _recalculate_row_amount(cdt, cdn);
            }
        }
    });
}

function _fetch_valuation_rates_for_all_items(frm) {
    (frm.doc.items || []).forEach(function (item) {
        if (item.item_code) {
            _fetch_valuation_rate(frm, item.doctype, item.name);
        }
    });
}

function _recalculate_row_amount(cdt, cdn) {
    let row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, 'basic_amount', flt(row.qty) * flt(row.basic_rate));
    frappe.model.set_value(cdt, cdn, 'transfer_qty', flt(row.qty) * flt(row.conversion_factor || 1));
}

function _setup_price_list_query(frm) {
    frm.set_query('price_list', function () {
        return { filters: { selling: 1, enabled: 1 } };
    });
}

function _fetch_price_list_rate(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row.item_code || !frm.doc.price_list) return;
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Item Price',
            filters: { item_code: row.item_code, price_list: frm.doc.price_list },
            fieldname: 'price_list_rate',
        },
        callback: function (r) {
            if (r.message && r.message.price_list_rate) {
                frappe.model.set_value(cdt, cdn, 'basic_rate', r.message.price_list_rate);
                frappe.model.set_value(cdt, cdn, 'valuation_rate', r.message.price_list_rate);
                _recalculate_row_amount(cdt, cdn);
            }
        }
    });
}

function _fetch_price_list_rates_for_all_items(frm) {
    (frm.doc.items || []).forEach(function (item) {
        if (item.item_code) {
            _fetch_price_list_rate(frm, item.doctype, item.name);
        }
    });
}
