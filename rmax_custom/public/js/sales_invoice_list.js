/**
 * RMAX Custom: Sales Invoice List View
 *
 * When is_return=1 filter is active, the "+ Add" button becomes "New Credit Note"
 * and prompts for the original invoice to create a proper return.
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

frappe.listview_settings["Sales Invoice"].refresh = function (listview) {
    if (_orig_si_refresh) _orig_si_refresh(listview);

    if (_si_is_return_filter_active(listview)) {
        listview.page.set_primary_action(
            __("New Credit Note"),
            function () {
                _show_return_dialog("Sales Invoice", "Credit Note");
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

function _show_return_dialog(doctype, label) {
    var d = new frappe.ui.Dialog({
        title: __("Create {0}", [__(label)]),
        fields: [
            {
                fieldname: "source_invoice",
                fieldtype: "Link",
                label: __("Original {0}", [__(doctype)]),
                options: doctype,
                reqd: 1,
                get_query: function () {
                    return {
                        filters: {
                            docstatus: 1,
                            is_return: 0,
                            company: frappe.defaults.get_default("company"),
                        }
                    };
                },
                description: __("Select the original invoice to create a return against")
            }
        ],
        primary_action_label: __("Create"),
        primary_action: function (values) {
            d.hide();
            frappe.call({
                method: "erpnext.accounts.doctype."
                    + frappe.model.scrub(doctype) + "."
                    + frappe.model.scrub(doctype)
                    + ".make_sales_return",
                args: { source_name: values.source_invoice },
                freeze: true,
                freeze_message: __("Creating {0}...", [__(label)]),
                callback: function (r) {
                    if (r.message) {
                        var doc = frappe.model.sync(r.message)[0];
                        frappe.set_route("Form", doc.doctype, doc.name);
                    }
                }
            });
        }
    });
    d.show();
}
