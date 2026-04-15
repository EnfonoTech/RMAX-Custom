/**
 * RMAX Custom: Material Request DocType JS
 * Loaded via doctype_js hook (no bench build needed).
 *
 * - Hides standard Material Transfer / Pick List buttons
 * - Adds "Stock Transfer" button ONLY for source warehouse branch users
 */

frappe.ui.form.on("Material Request", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1 && frm.doc.material_request_type === "Material Transfer") {
            _rmax_setup_buttons(frm);
        }
        _rmax_highlight_urgent_items(frm);
    },
});

// Auto-sync: if ANY item is urgent, tick the parent checkbox too
frappe.ui.form.on("Material Request Item", {
    custom_is_urgent: function (frm, cdt, cdn) {
        _rmax_sync_urgent_to_parent(frm);
        _rmax_highlight_urgent_items(frm);
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
    if (frm.doc.status === "Stopped" || flt(frm.doc.per_ordered) >= 100) return;
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
