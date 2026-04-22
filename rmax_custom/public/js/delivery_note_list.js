/**
 * RMAX Custom: Delivery Note list view — bulk consolidation action.
 *
 * Adds a menu action that takes the currently ticked submitted
 * inter-company Delivery Notes and builds a single Draft Sales Invoice
 * from the selling (Head Office) company. Existing SI on_submit hook
 * then auto-creates the matching Purchase Invoice on the receiving
 * side.
 */

frappe.listview_settings["Delivery Note"] = Object.assign(
    frappe.listview_settings["Delivery Note"] || {},
    {
        onload: function (listview) {
            listview.page.add_actions_menu_item(
                __("Create Inter-Company Sales Invoice"),
                function () {
                    _rmax_create_inter_company_si(listview);
                }
            );
        },
    }
);

function _rmax_create_inter_company_si(listview) {
    const selected = listview.get_checked_items().map((row) => row.name);
    if (!selected.length) {
        frappe.msgprint(__("Select at least one Delivery Note first."));
        return;
    }

    frappe.confirm(
        __(
            "Consolidate {0} Delivery Note(s) into one Draft Sales Invoice?",
            [selected.length]
        ),
        function () {
            frappe.call({
                method: "rmax_custom.inter_company_dn.create_si_from_multiple_dns",
                args: {
                    delivery_note_names: selected,
                },
                freeze: true,
                freeze_message: __("Building Sales Invoice..."),
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("Created {0}", [r.message]),
                            indicator: "green",
                        });
                        frappe.set_route("Form", "Sales Invoice", r.message);
                    }
                },
            });
        }
    );
}
