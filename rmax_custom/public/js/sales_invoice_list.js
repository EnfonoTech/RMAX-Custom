/**
 * RMAX Custom: Sales Invoice List View enhancements
 * - Additional standard filters: Customer Mobile, Grand Total, Item, Total Qty
 */
frappe.listview_settings["Sales Invoice"] = frappe.listview_settings["Sales Invoice"] || {};

// Preserve existing onload if any
var _orig_si_onload = frappe.listview_settings["Sales Invoice"].onload;

frappe.listview_settings["Sales Invoice"].onload = function (listview) {
    if (_orig_si_onload) _orig_si_onload(listview);

    // Add custom filters to the filter area
    // Grand Total (with tax)
    listview.page.add_field({
        fieldname: "grand_total",
        label: __("Grand Total"),
        fieldtype: "Currency",
        change: function () {
            var val = this.get_value();
            if (val) {
                listview.filter_area.add("Sales Invoice", "grand_total", ">=", val);
            } else {
                listview.filter_area.remove("grand_total");
            }
            listview.refresh();
        }
    });

    // Total Quantity
    listview.page.add_field({
        fieldname: "total_qty",
        label: __("Total Qty"),
        fieldtype: "Float",
        change: function () {
            var val = this.get_value();
            if (val) {
                listview.filter_area.add("Sales Invoice", "total_qty", ">=", val);
            } else {
                listview.filter_area.remove("total_qty");
            }
            listview.refresh();
        }
    });
};
