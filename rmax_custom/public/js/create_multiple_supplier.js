frappe.ui.form.on("Item", {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button("Add Multiple Suppliers", function () {
            open_multiple_suppliers_dialog(frm);
        });
    }
});



function open_multiple_suppliers_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: "Add Suppliers for this Item",
        size: "large",
        fields: [
            {
                fieldname: "suppliers_table",
                fieldtype: "Table",
                label: "Suppliers",
                in_place_edit: true,
                cannot_add_rows: false,

                fields: [
                    {
                        fieldname: "supplier",
                        fieldtype: "Link",
                        label: "Supplier",
                        options: "Supplier",
                        in_list_view: 1,
                        reqd: 1
                    }
                ]
            }
        ],
        primary_action_label: "Create Party Specific Items",
        primary_action(values) {

            if (!values.suppliers_table || values.suppliers_table.length === 0) {
                frappe.msgprint("Please add suppliers");
                return;
            }

            frappe.call({
                method: "rmax_custom.api.item.create_party_specific_items",
                args: {
                    item: frm.doc.name,
                    suppliers: values.suppliers_table
                },
                callback: function () {

                    frappe.msgprint("Party Specific Items Created Successfully");

                    d.hide();

                    frm.reload_doc();
                }
            });
        }
    });

    d.show();
}