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
