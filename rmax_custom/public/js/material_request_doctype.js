/**
 * RMAX Custom: Material Request DocType JS
 * Loaded via doctype_js hook (no bench build needed).
 *
 * - Hides standard Material Transfer / Pick List buttons
 * - Adds "Stock Transfer" button ONLY for source warehouse branch users
 * - Shows available qty (source + target) in items child table
 */

frappe.ui.form.on("Material Request", {
    refresh: function (frm) {
        // Clean up any old transfer-status HTML from previous sessions
        frm.fields_dict.items.$wrapper.parent().find(".rmax-transfer-status").remove();

        if (frm.doc.docstatus === 1 && frm.doc.material_request_type === "Material Transfer") {
            _rmax_setup_buttons(frm);
        }
        _rmax_highlight_urgent_items(frm);

        // Fetch available qty for items in child table
        if (frm.doc.material_request_type === "Material Transfer") {
            _rmax_fetch_available_qty(frm);
        }
    },
    set_from_warehouse: function (frm) {
        _rmax_fetch_available_qty(frm);
    },
    set_warehouse: function (frm) {
        _rmax_fetch_available_qty(frm);
    },
});

// Auto-sync: if ANY item is urgent, tick the parent checkbox too
frappe.ui.form.on("Material Request Item", {
    custom_is_urgent: function (frm, cdt, cdn) {
        _rmax_sync_urgent_to_parent(frm);
        _rmax_highlight_urgent_items(frm);
    },
    item_code: function (frm, cdt, cdn) {
        // Fetch available qty when item is added/changed
        setTimeout(function () {
            _rmax_fetch_available_qty(frm);
        }, 500);
    },
    items_remove: function (frm) {
        _rmax_sync_urgent_to_parent(frm);
    },
});

function _rmax_sync_urgent_to_parent(frm) {
    var any_urgent = (frm.doc.items || []).some(function (item) {
        return item.custom_is_urgent;
    });
    if (frm.doc.custom_is_urgent !== any_urgent) {
        frm.set_value("custom_is_urgent", any_urgent ? 1 : 0);
    }
}

function _rmax_highlight_urgent_items(frm) {
    // Highlight urgent item rows with a red left border
    setTimeout(function () {
        (frm.doc.items || []).forEach(function (item) {
            var $row = frm.fields_dict.items.grid.grid_rows_by_docname[item.name];
            if ($row && $row.row) {
                if (item.custom_is_urgent) {
                    $($row.row).css({
                        "border-left": "3px solid #e94560",
                        "background-color": "#fff5f5"
                    });
                } else {
                    $($row.row).css({
                        "border-left": "",
                        "background-color": ""
                    });
                }
            }
        });
    }, 300);
}

// ─── Available Qty in Child Table ────────────────────────────

function _rmax_fetch_available_qty(frm) {
    var source_wh = frm.doc.set_from_warehouse;
    var target_wh = frm.doc.set_warehouse;

    if (!source_wh && !target_wh) return;
    if (!frm.doc.items || !frm.doc.items.length) return;

    // Collect unique item codes
    var item_codes = [];
    (frm.doc.items || []).forEach(function (item) {
        if (item.item_code && item_codes.indexOf(item.item_code) === -1) {
            item_codes.push(item.item_code);
        }
    });

    if (!item_codes.length) return;

    frappe.call({
        method: "rmax_custom.api.material_request.get_available_qty_for_items",
        args: {
            items: JSON.stringify(item_codes),
            source_warehouse: source_wh || "",
            target_warehouse: target_wh || ""
        },
        callback: function (r) {
            if (!r.message) return;
            var qty_map = r.message;

            // Set values directly on doc to avoid marking form dirty
            (frm.doc.items || []).forEach(function (item) {
                if (item.item_code && qty_map[item.item_code]) {
                    item.custom_source_available_qty = flt(qty_map[item.item_code].source);
                    item.custom_target_available_qty = flt(qty_map[item.item_code].target);
                }
            });

            frm.refresh_field("items");

            // Color-code available qty cells
            setTimeout(function () {
                _rmax_color_available_qty(frm);
                _rmax_highlight_urgent_items(frm);
            }, 200);
        }
    });
}

function _rmax_color_available_qty(frm) {
    (frm.doc.items || []).forEach(function (item) {
        var $row = frm.fields_dict.items.grid.grid_rows_by_docname[item.name];
        if (!$row || !$row.row) return;

        var needed = flt(item.qty);
        var source_avl = flt(item.custom_source_available_qty);

        // Color the source available qty cell
        var $source_cell = $($row.row).find('[data-fieldname="custom_source_available_qty"]');
        if ($source_cell.length) {
            if (needed > 0 && source_avl < needed) {
                $source_cell.css("color", "#e94560");
            } else if (needed > 0 && source_avl >= needed) {
                $source_cell.css("color", "#10b981");
            }
        }
    });
}

// ─── Stock Transfer Button ───────────────────────────────────

function _rmax_setup_buttons(frm) {
    // Get source warehouse
    var source_wh = frm.doc.set_from_warehouse;
    if (!source_wh && frm.doc.items && frm.doc.items.length) {
        source_wh = frm.doc.items[0].from_warehouse;
    }

    // Check if user can create Stock Transfer (async)
    frappe.call({
        method: "rmax_custom.api.material_request.can_create_stock_transfer",
        args: { source_warehouse: source_wh || "" },
        callback: function (r) {
            _rmax_hide_standard_buttons(frm);

            if (r.message) {
                _rmax_add_stock_transfer_button(frm);
            }

            setTimeout(function () {
                _rmax_hide_standard_buttons(frm);
            }, 500);
        },
        error: function () {
            _rmax_hide_standard_buttons(frm);
        },
    });
}

function _rmax_hide_standard_buttons(frm) {
    var labels_to_hide = [
        __("Material Transfer"),
        __("Material Transfer (In Transit)"),
        __("Pick List"),
    ];

    labels_to_hide.forEach(function (label) {
        if (frm.custom_buttons && frm.custom_buttons[label]) {
            frm.custom_buttons[label].addClass("hidden");
        }
    });

    frm.page.inner_toolbar.find(".dropdown-item, .dropdown-menu a").each(function () {
        var text = $(this).text().trim();
        if (
            text === "Material Transfer" ||
            text === "Material Transfer (In Transit)" ||
            text === "Pick List"
        ) {
            $(this).addClass("hidden");
        }
    });
}

function _rmax_add_stock_transfer_button(frm) {
    if (frm.doc.status === "Stopped") return;
    if (frm.custom_buttons && frm.custom_buttons[__("Stock Transfer")]) return;

    frm.add_custom_button(
        __("Stock Transfer"),
        function () {
            frappe.call({
                method: "rmax_custom.api.material_request.create_stock_transfer_from_mr",
                args: { material_request: frm.doc.name },
                freeze: true,
                freeze_message: __("Creating Stock Transfer..."),
                callback: function (r) {
                    if (r.message) {
                        frappe.set_route("Form", "Stock Transfer", r.message);
                    }
                },
            });
        },
        __("Create")
    );
}
