/**
 * RMAX Custom: Purchase Invoice List View
 *
 * When is_return=1 filter is active, the "+ Add" button becomes "+ New Debit Note"
 * and creates a Purchase Invoice with is_return=1 pre-set.
 */
frappe.listview_settings["Purchase Invoice"] = frappe.listview_settings["Purchase Invoice"] || {};

var _orig_pi_refresh = frappe.listview_settings["Purchase Invoice"].refresh;

frappe.listview_settings["Purchase Invoice"].refresh = function (listview) {
    if (_orig_pi_refresh) _orig_pi_refresh(listview);

    // Check if is_return filter is active
    var filters = listview.filter_area ? listview.filter_area.get() : [];
    var is_return_active = false;
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
                frappe.new_doc("Purchase Invoice");
                // Wait for form to load, then tick is_return
                var attempts = 0;
                var check = setInterval(function () {
                    attempts++;
                    if (attempts > 50) { clearInterval(check); return; }
                    if (cur_frm && cur_frm.doc.doctype === "Purchase Invoice" && cur_frm.doc.__islocal) {
                        clearInterval(check);
                        cur_frm.set_value("is_return", 1);
                        cur_frm.dirty();
                    }
                }, 100);
            }
        );
    }
};
