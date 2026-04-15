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
            _rmax_show_transfer_status(frm);
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

// ─── Transfer Status & Available Qty Section ─────────────────

function _rmax_show_transfer_status(frm) {
    // Remove old status section if any
    frm.fields_dict.items.$wrapper.parent().find(".rmax-transfer-status").remove();

    frappe.call({
        method: "rmax_custom.api.material_request.get_mr_transfer_status",
        args: { material_request: frm.doc.name },
        callback: function (r) {
            if (!r.message || !r.message.length) return;

            var items = r.message;
            var has_any_transfer = items.some(function (d) { return d.transferred_qty > 0; });

            var html = '<div class="rmax-transfer-status" style="margin-top:15px;padding:10px 15px;border:1px solid #d1d8dd;border-radius:6px;background:#f8f9fa;">';
            html += '<h6 style="margin:0 0 8px;font-weight:600;color:#333;">📦 Stock & Transfer Status</h6>';
            html += '<table class="table table-sm table-bordered" style="margin:0;font-size:12px;">';
            html += '<thead><tr style="background:#e9ecef;">';
            html += '<th>Item</th>';
            html += '<th style="width:75px;text-align:right;">Requested</th>';
            html += '<th style="width:90px;text-align:right;">Source Avl</th>';
            html += '<th style="width:90px;text-align:right;">Target Avl</th>';

            if (has_any_transfer) {
                html += '<th style="width:90px;text-align:right;">Transferred</th>';
                html += '<th style="width:75px;text-align:right;">Pending</th>';
            }

            html += '<th style="width:70px;text-align:center;">Status</th>';
            html += '</tr></thead><tbody>';

            items.forEach(function (d) {
                var row_style = '';
                var badge = '';

                if (has_any_transfer && d.pending_qty <= 0) {
                    row_style = ' style="background:#f0fdf4;"';
                    badge = '<span style="background:#10b981;color:#fff;padding:1px 5px;border-radius:3px;font-size:10px;">DONE</span>';
                } else if (has_any_transfer && d.transferred_qty > 0) {
                    row_style = ' style="background:#fffbeb;"';
                    badge = '<span style="background:#f59e0b;color:#fff;padding:1px 5px;border-radius:3px;font-size:10px;">PARTIAL</span>';
                } else if (d.source_available < d.requested_qty) {
                    badge = '<span style="background:#ef4444;color:#fff;padding:1px 5px;border-radius:3px;font-size:10px;">LOW</span>';
                } else {
                    badge = '<span style="background:#10b981;color:#fff;padding:1px 5px;border-radius:3px;font-size:10px;">OK</span>';
                }

                // Color source available qty
                var src_color = d.source_available >= d.requested_qty ? '#10b981' : '#e94560';

                html += '<tr' + row_style + '>';
                html += '<td>' + d.item_code + ' — ' + d.item_name + '</td>';
                html += '<td style="text-align:right;">' + d.requested_qty + '</td>';
                html += '<td style="text-align:right;font-weight:600;color:' + src_color + ';">' + d.source_available + '</td>';
                html += '<td style="text-align:right;font-weight:600;color:#6c757d;">' + d.target_available + '</td>';

                if (has_any_transfer) {
                    html += '<td style="text-align:right;font-weight:600;">' + d.transferred_qty + '</td>';
                    html += '<td style="text-align:right;font-weight:600;color:' + (d.pending_qty > 0 ? '#e94560' : '#10b981') + ';">' + d.pending_qty + '</td>';
                }

                html += '<td style="text-align:center;">' + badge + '</td>';
                html += '</tr>';
            });

            html += '</tbody></table>';

            // Show warehouse info
            var source_wh = items[0] && items[0].source_warehouse;
            var target_wh = items[0] && items[0].target_warehouse;
            var info_parts = [];
            if (source_wh) info_parts.push('Source: <b>' + source_wh + '</b>');
            if (target_wh) info_parts.push('Target: <b>' + target_wh + '</b>');
            if (info_parts.length) {
                html += '<div style="margin-top:6px;font-size:11px;color:#6c757d;">' + info_parts.join(' &nbsp;|&nbsp; ') + '</div>';
            }

            html += '</div>';

            frm.fields_dict.items.$wrapper.after(html);
        }
    });
}
