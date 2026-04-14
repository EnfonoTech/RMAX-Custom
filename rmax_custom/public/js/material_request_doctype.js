/**
 * RMAX Custom: Material Request DocType JS
 * Loaded via doctype_js hook (no bench build needed).
 *
 * - Hides standard Material Transfer / Pick List buttons
 * - Adds "Stock Transfer" button under Create
 */

frappe.ui.form.on("Material Request", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1 && frm.doc.material_request_type === "Material Transfer") {
            // Wait for ERPNext's buttons to render first
            setTimeout(function () {
                _rmax_hide_standard_buttons(frm);
                _rmax_add_stock_transfer_button(frm);
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
        // Hide from custom_buttons registry
        if (frm.custom_buttons && frm.custom_buttons[label]) {
            frm.custom_buttons[label].addClass("hidden");
        }
    });

    // Also hide from dropdown menu items inside "Create" group
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

    // Don't add duplicate button
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
