// Copyright (c) 2026, Enfono and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Transfer', {

    onload: function(frm) {
        if (frm.is_new()) {
            set_default_target(frm);
        }
        _setup_st_warehouse_queries(frm);
    },
    refresh: function(frm) {
        if (frm.doc.__islocal && !frm.doc.__source_fixed) {
            setTimeout(() => {
                frm.set_value('set_target_warehouse', '');
                frm.doc.__source_fixed = true;
            }, 200);
        }

        // Fetch available qty once on load (don't re-fetch on every refresh)
        if (!frm.doc.__avail_qty_fetched && frm.doc.set_source_warehouse) {
            frm.doc.__avail_qty_fetched = true;
            _fetch_available_qty(frm);
        } else {
            // Just re-color existing data
            setTimeout(function() { _color_code_rows(frm); }, 200);
        }
    },
    set_source_warehouse: function(frm) {
        // Re-fetch available qty when source warehouse changes
        frm.doc.__avail_qty_fetched = false;
        _fetch_available_qty(frm);
    },
});


// ─── Available Qty: Fetch and Color-Code ──────────────────────

function _fetch_available_qty(frm) {
    var source_wh = frm.doc.set_source_warehouse;
    if (!source_wh || !frm.doc.items || !frm.doc.items.length) {
        return;
    }

    // Collect unique item codes
    var item_codes = [];
    (frm.doc.items || []).forEach(function(item) {
        if (item.item_code && item_codes.indexOf(item.item_code) === -1) {
            item_codes.push(item.item_code);
        }
    });

    if (!item_codes.length) return;

    // Remember dirty state before setting values
    var was_dirty = frm.dirty();

    frappe.call({
        method: "rmax_custom.rmax_custom.doctype.stock_transfer.stock_transfer.get_items_available_qty",
        args: {
            items: JSON.stringify(item_codes),
            warehouse: source_wh
        },
        callback: function(r) {
            if (!r.message) return;
            var qty_map = r.message;

            // Set values directly on the doc object to avoid marking dirty
            (frm.doc.items || []).forEach(function(item) {
                if (item.item_code && qty_map.hasOwnProperty(item.item_code)) {
                    item.available_qty = flt(qty_map[item.item_code]);
                }
            });

            frm.refresh_field("items");

            // Restore dirty state — available_qty is display-only
            if (!was_dirty) {
                frm.dirty_state_set = false;
                frm.save_disabled = false;
                frm.page.clear_indicator();
                // Remove "Not Saved" indicator
                $(frm.wrapper).find('.indicator-pill').remove();
                frm.page.set_indicator('');
            }

            setTimeout(function() {
                _color_code_rows(frm);
            }, 200);
        }
    });
}

function _color_code_rows(frm) {
    (frm.doc.items || []).forEach(function(item) {
        var $row = frm.fields_dict.items.grid.grid_rows_by_docname[item.name];
        if (!$row || !$row.row) return;

        var needed = flt(item.quantity);
        var available = flt(item.available_qty);

        if (needed > 0 && available < needed) {
            // Insufficient stock — red indicator
            $($row.row).css({
                "border-left": "3px solid #ef4444",
                "background-color": "#fef2f2"
            });
        } else if (needed > 0 && available >= needed) {
            // Sufficient stock — green indicator
            $($row.row).css({
                "border-left": "3px solid #10b981",
                "background-color": "#f0fdf4"
            });
        } else {
            $($row.row).css({
                "border-left": "",
                "background-color": ""
            });
        }
    });
}


// ─── Warehouse Queries ────────────────────────────────────────

function _setup_st_warehouse_queries(frm) {
    // Source warehouse: ONLY user's permitted warehouses
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
            frm.set_query('set_source_warehouse', function() {
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

    // Target warehouse: ANY warehouse (can send to any branch)
    frm.set_query('set_target_warehouse', function() {
        return {
            ignore_user_permissions: 1,
            filters: {
                company: frm.doc.company,
                is_group: 0,
                name: ["!=", frm.doc.set_source_warehouse]
            }
        };
    });
}

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


// ─── Item Field Handlers ──────────────────────────────────────

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

        // Fetch available qty for this item
        _fetch_single_item_qty(frm, row);
    },
    quantity: function(frm, cdt, cdn) {
        // Re-color when quantity changes
        setTimeout(function() { _color_code_rows(frm); }, 100);
    },
    uom: function(frm, cdt, cdn) {
        trigger_conversion(frm, cdt, cdn);
    }
});

function _fetch_single_item_qty(frm, row) {
    var source_wh = frm.doc.set_source_warehouse;
    if (!source_wh || !row.item_code) return;

    frappe.call({
        method: "rmax_custom.rmax_custom.doctype.stock_transfer.stock_transfer.get_items_available_qty",
        args: {
            items: JSON.stringify([row.item_code]),
            warehouse: source_wh
        },
        callback: function(r) {
            if (r.message && r.message[row.item_code] !== undefined) {
                // Set directly to avoid extra dirty marking
                row.available_qty = flt(r.message[row.item_code]);
                frm.refresh_field("items");
                setTimeout(function() { _color_code_rows(frm); }, 200);
            }
        }
    });
}

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
