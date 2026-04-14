/**
 * RMAX Custom: Material Request DocType JS
 * Loaded via doctype_js hook (no bench build needed).
 *
 * - Hides standard Material Transfer / Pick List buttons
 * - Adds "Stock Transfer" button ONLY for source warehouse branch users
 *
 * Flow: Requester creates MR → Source branch user creates ST → Target branch user approves
 */

frappe.ui.form.on("Material Request", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1 && frm.doc.material_request_type === "Material Transfer") {
            setTimeout(function () {
                _rmax_hide_standard_buttons(frm);
                _rmax_maybe_add_stock_transfer_button(frm);
            }, 300);
        }
    },
});

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

function _rmax_maybe_add_stock_transfer_button(frm) {
    if (frm.doc.status === "Stopped" || flt(frm.doc.per_ordered) >= 100) return;
    if (frm.custom_buttons && frm.custom_buttons[__("Stock Transfer")]) return;

    // Get source warehouse from MR (set_from_warehouse or from item rows)
    var source_wh = frm.doc.set_from_warehouse;
    if (!source_wh && frm.doc.items && frm.doc.items.length) {
        source_wh = frm.doc.items[0].from_warehouse;
    }

    if (!source_wh) {
        _rmax_add_stock_transfer_button(frm);
        return;
    }

    // Check if current user is from the source warehouse's branch
    // Uses a whitelisted method to avoid User Permission read access issues
    frappe.call({
        method: "rmax_custom.api.material_request.can_create_stock_transfer",
        args: {
            source_warehouse: source_wh,
        },
        async: false,
        callback: function (r) {
            if (r.message) {
                _rmax_add_stock_transfer_button(frm);
            }
        },
    });
}

function _rmax_add_stock_transfer_button(frm) {
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
