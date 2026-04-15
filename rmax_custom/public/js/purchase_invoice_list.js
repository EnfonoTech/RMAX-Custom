/**
 * RMAX Custom: Purchase Invoice List View
 *
 * When is_return=1 filter is active, the "+ Add" button becomes "New Debit Note"
 * and creates a Purchase Invoice with is_return=1 pre-set.
 */
frappe.listview_settings["Purchase Invoice"] = frappe.listview_settings["Purchase Invoice"] || {};

var _orig_pi_refresh = frappe.listview_settings["Purchase Invoice"].refresh;

frappe.listview_settings["Purchase Invoice"].refresh = function (listview) {
    if (_orig_pi_refresh) _orig_pi_refresh(listview);

    var is_return_active = false;
    var filters = listview.filter_area ? listview.filter_area.get() : [];
    for (var i = 0; i < filters.length; i++) {
        if (filters[i][1] === "is_return" && filters[i][3] == 1) {
            is_return_active = true;
            break;
        }
    }
    if (!is_return_active) {
        var route = frappe.get_route();
        if (route && route.length > 2) {
            for (var j = 2; j < route.length; j++) {
                if ((route[j] || "").indexOf("is_return=1") !== -1) {
                    is_return_active = true;
                    break;
                }
            }
        }
    }

    if (is_return_active) {
        listview.page.set_primary_action(
            __("New Debit Note"),
            function () {
                var doc = frappe.model.get_new_doc("Purchase Invoice");
                doc.is_return = 1;
                frappe.set_route("Form", "Purchase Invoice", doc.name);
            }
        );
    }
};
