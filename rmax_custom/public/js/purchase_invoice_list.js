/**
 * RMAX Custom: Purchase Invoice List View
 *
 * When filtered by is_return=1, overrides the "+ Add" button
 * to create a Debit Note (Purchase Invoice with is_return=1).
 */
frappe.listview_settings["Purchase Invoice"] = frappe.listview_settings["Purchase Invoice"] || {};

var _orig_pi_onload = frappe.listview_settings["Purchase Invoice"].onload;

frappe.listview_settings["Purchase Invoice"].onload = function (listview) {
    if (_orig_pi_onload) _orig_pi_onload(listview);

    _setup_pi_return_action(listview);

    listview.page.wrapper.on("change", ".frappe-control[data-fieldname='is_return']", function () {
        setTimeout(function () {
            _setup_pi_return_action(listview);
        }, 300);
    });
};


function _setup_pi_return_action(listview) {
    var is_return_active = false;
    (listview.filter_area ? listview.filter_area.get() : []).forEach(function (f) {
        if (f[1] === "is_return" && f[3] == 1) {
            is_return_active = true;
        }
    });

    var route = frappe.get_route();
    if (route && route.length > 2) {
        var route_str = route.slice(2).join("/");
        if (route_str.indexOf("is_return") !== -1) {
            is_return_active = true;
        }
    }

    if (is_return_active) {
        listview.page.set_primary_action(
            __("+ New Debit Note"),
            function () {
                frappe.new_doc("Purchase Invoice", { is_return: 1 });
            },
            "add"
        );
    }
}
