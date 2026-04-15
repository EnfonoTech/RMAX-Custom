/**
 * RMAX Custom: Sales Invoice List View
 *
 * When is_return=1 filter is active, the "+ Add" button becomes "New Credit Note"
 * and creates a Sales Invoice with is_return=1 pre-set.
 */
frappe.listview_settings["Sales Invoice"] = frappe.listview_settings["Sales Invoice"] || {};

var _orig_si_onload = frappe.listview_settings["Sales Invoice"].onload;
var _orig_si_refresh = frappe.listview_settings["Sales Invoice"].refresh;

frappe.listview_settings["Sales Invoice"].onload = function (listview) {
    if (_orig_si_onload) _orig_si_onload(listview);

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

frappe.listview_settings["Sales Invoice"].refresh = function (listview) {
    if (_orig_si_refresh) _orig_si_refresh(listview);

    if (_si_is_return_filter_active(listview)) {
        listview.page.set_primary_action(
            __("New Credit Note"),
            function () {
                // Flag that we want a return — picked up by form event below
                window._rmax_create_return = "Sales Invoice";
                frappe.new_doc("Sales Invoice");
            }
        );
    }
};

function _si_is_return_filter_active(listview) {
    var filters = listview.filter_area ? listview.filter_area.get() : [];
    for (var i = 0; i < filters.length; i++) {
        if (filters[i][1] === "is_return" && filters[i][3] == 1) return true;
    }
    var route = frappe.get_route();
    if (route && route.length > 2) {
        for (var j = 2; j < route.length; j++) {
            if ((route[j] || "").indexOf("is_return=1") !== -1) return true;
        }
    }
    return false;
}

// Listen for form render — set is_return after the form is fully loaded
$(document).on("form-refresh", function (e, frm) {
    if (window._rmax_create_return && frm.doc.__islocal) {
        if (frm.doc.doctype === window._rmax_create_return) {
            delete window._rmax_create_return;
            frm.set_value("is_return", 1);
        }
    }
});
