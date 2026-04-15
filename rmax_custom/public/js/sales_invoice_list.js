/**
 * RMAX Custom: Sales Invoice List View
 *
 * Standard filters (Grand Total, Total Qty, Mobile No) are added via
 * Property Setters (in_standard_filter=1) — no JS needed for those.
 *
 * This file handles any additional list view customizations.
 */
frappe.listview_settings["Sales Invoice"] = frappe.listview_settings["Sales Invoice"] || {};

var _orig_si_onload = frappe.listview_settings["Sales Invoice"].onload;

frappe.listview_settings["Sales Invoice"].onload = function (listview) {
    if (_orig_si_onload) _orig_si_onload(listview);

    // If list is filtered by is_return=1, override the "+ Add" button
    // to create a Credit Note (is_return=1, naming_series for returns)
    _setup_return_primary_action(listview, "Sales Invoice", "Credit Note");

    // Re-check when filters change
    listview.page.wrapper.on("change", ".frappe-control[data-fieldname='is_return']", function () {
        setTimeout(function () {
            _setup_return_primary_action(listview, "Sales Invoice", "Credit Note");
        }, 300);
    });

    // Inject CSS to organize the list view layout
    if (!document.getElementById("rmax-list-style")) {
        var style = document.createElement("style");
        style.id = "rmax-list-style";
        style.textContent = [
            /* Standard filters area: left-aligned, wrap nicely */
            ".frappe-list .standard-filter-section {",
            "  display: flex !important;",
            "  flex-wrap: wrap !important;",
            "  gap: 6px !important;",
            "  align-items: center !important;",
            "  flex: 1 !important;",
            "}",
            /* Filter controls row: space between filters and buttons */
            ".frappe-list .list-row-head .level-left {",
            "  flex: 1 !important;",
            "}",
            /* Keep filter/sort buttons right-aligned */
            ".frappe-list .list-row-head .level-right {",
            "  margin-left: auto !important;",
            "  flex-shrink: 0 !important;",
            "}",
            /* Page head fields (added by page.add_field) — hide duplicates */
            ".page-head .page-form .frappe-control[data-fieldname='grand_total'],",
            ".page-head .page-form .frappe-control[data-fieldname='total_qty'] {",
            "  display: none !important;",
            "}",
        ].join("\n");
        document.head.appendChild(style);
    }
};


/**
 * If the list view has is_return=1 filter active, override the primary action
 * button to create a return document (Credit Note / Debit Note).
 */
function _setup_return_primary_action(listview, doctype, return_label) {
    // Check if is_return filter is active
    var is_return_active = false;
    (listview.filter_area ? listview.filter_area.get() : []).forEach(function (f) {
        if (f[1] === "is_return" && f[3] == 1) {
            is_return_active = true;
        }
    });

    // Also check URL route params
    var route = frappe.get_route();
    if (route && route.length > 2) {
        var route_str = route.slice(2).join("/");
        if (route_str.indexOf("is_return") !== -1) {
            is_return_active = true;
        }
    }

    if (is_return_active) {
        listview.page.set_primary_action(
            __("+ New {0}", [__(return_label)]),
            function () {
                frappe.new_doc(doctype, { is_return: 1 });
            },
            "add"
        );
    }
}
