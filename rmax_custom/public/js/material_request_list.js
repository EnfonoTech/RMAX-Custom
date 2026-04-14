frappe.listview_settings["Material Request"] = frappe.listview_settings["Material Request"] || {};

// Preserve any existing get_indicator
var _orig_indicator = frappe.listview_settings["Material Request"].get_indicator;

frappe.listview_settings["Material Request"].get_indicator = function (doc) {
    if (doc.custom_is_urgent) {
        return [__("Urgent"), "red", "custom_is_urgent,=,1"];
    }
    if (_orig_indicator) {
        return _orig_indicator(doc);
    }
};
