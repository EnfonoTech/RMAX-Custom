/**
 * RMAX Custom: Sales Invoice List View
 *
 * Standard filters (Grand Total, Total Qty, Mobile No) are added via
 * Property Setters (in_standard_filter=1) — no JS needed for those.
 *
 * When is_return=1 filter is active, the "+ Add" button becomes "+ New Credit Note"
 * and creates a Sales Invoice with is_return=1 pre-set.
 */
frappe.listview_settings["Sales Invoice"] = frappe.listview_settings["Sales Invoice"] || {};

var _orig_si_onload = frappe.listview_settings["Sales Invoice"].onload;
var _orig_si_refresh = frappe.listview_settings["Sales Invoice"].refresh;

frappe.listview_settings["Sales Invoice"].onload = function (listview) {
    if (_orig_si_onload) _orig_si_onload(listview);

    // Inject CSS to organize the list view layout
    if (!document.getElementById("rmax-list-style")) {
        var style = document.createElement("style");
        style.id = "rmax-list-style";
        style.textContent = [
            ".frappe-list .standard-filter-section {",
            "  display: flex !important;",
            "  flex-wrap: wrap !important;",
            "  gap: 6px !important;",
            "  align-items: center !important;",
            "  flex: 1 !important;",
            "}",
            ".frappe-list .list-row-head .level-left {",
            "  flex: 1 !important;",
            "}",
            ".frappe-list .list-row-head .level-right {",
            "  margin-left: auto !important;",
            "  flex-shrink: 0 !important;",
            "}",
            ".page-head .page-form .frappe-control[data-fieldname='grand_total'],",
            ".page-head .page-form .frappe-control[data-fieldname='total_qty'] {",
            "  display: none !important;",
            "}",
        ].join("\n");
        document.head.appendChild(style);
    }
};

// refresh fires AFTER every list render — this is where we override the primary action
// so Frappe's own set_primary_action doesn't stomp our button
frappe.listview_settings["Sales Invoice"].refresh = function (listview) {
    if (_orig_si_refresh) _orig_si_refresh(listview);

    // Check if is_return filter is active
    if (_is_return_filter_active(listview)) {
        listview.page.set_primary_action(
            __("+ New Credit Note"),
            function () {
                frappe.new_doc("Sales Invoice", { is_return: 1 });
            },
            "add"
        );
    }
};

function _is_return_filter_active(listview) {
    // Check applied filters
    var filters = listview.filter_area ? listview.filter_area.get() : [];
    for (var i = 0; i < filters.length; i++) {
        if (filters[i][1] === "is_return" && filters[i][3] == 1) {
            return true;
        }
    }
    // Also check URL route
    var route = frappe.get_route();
    if (route && route.length > 2) {
        for (var j = 2; j < route.length; j++) {
            if ((route[j] || "").indexOf("is_return=1") !== -1) {
                return true;
            }
        }
    }
    return false;
}
