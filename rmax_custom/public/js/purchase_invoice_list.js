/**
 * RMAX Custom: Purchase Invoice List View
 *
 * When is_return=1 filter is active, the "+ Add" button becomes "New Debit Note"
 * and prompts for the original invoice to create a proper return.
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
                var d = new frappe.ui.Dialog({
                    title: __("Create Debit Note"),
                    fields: [
                        {
                            fieldname: "source_invoice",
                            fieldtype: "Link",
                            label: __("Original Purchase Invoice"),
                            options: "Purchase Invoice",
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
                            method: "erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_debit_note",
                            args: { source_name: values.source_invoice },
                            freeze: true,
                            freeze_message: __("Creating Debit Note..."),
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
        );
    }
};
