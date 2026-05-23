/**
 * RMAX Custom: Create New Supplier dialog.
 * Registered on Purchase Invoice, Purchase Order, Purchase Receipt.
 *
 * Fields: Supplier Name (required), Mobile, Email, VAT (tax_id), Address (optional).
 */

frappe.ui.form.on("Purchase Invoice", {
    refresh: function (frm) {
        add_create_supplier_button(frm, { supplierField: "supplier" });
    },
});

frappe.ui.form.on("Purchase Order", {
    refresh: function (frm) {
        add_create_supplier_button(frm, { supplierField: "supplier" });
    },
});

frappe.ui.form.on("Purchase Receipt", {
    refresh: function (frm) {
        add_create_supplier_button(frm, { supplierField: "supplier" });
    },
});

function add_create_supplier_button(frm, opts) {
    opts = opts || {};
    const supplierField = opts.supplierField || "supplier";

    if (frm.doc.docstatus !== 0) return;
    if (!frm.fields_dict[supplierField]) return;

    const $field = frm.fields_dict[supplierField].$wrapper;
    const $parent = $field.parent();

    if ($parent.find(".create-supplier-btn").length) return;

    const $btn = $(`
        <button type="button"
            class="btn btn-sm btn-secondary create-supplier-btn"
            style="margin-bottom: 5px;">
            <i class="fa fa-plus"></i> Create New Supplier
        </button>
    `);
    $btn.on("click", function () {
        open_create_supplier_dialog(frm, opts);
    });
    $field.before($btn);
}

function open_create_supplier_dialog(frm, opts) {
    opts = opts || {};
    const supplierField = opts.supplierField || "supplier";
    const company = frm.doc.company || frappe.defaults.get_default("company");

    frappe.db.get_value("Company", company, ["country"], function (r) {
        const country = r.country;

        const d = new frappe.ui.Dialog({
            title: "Create New Supplier",
            size: "large",

            fields: [
                {
                    fieldname: "supplier_name",
                    fieldtype: "Data",
                    label: "Supplier Name",
                    reqd: 1,
                },
                {
                    fieldname: "mobile_no",
                    fieldtype: "Data",
                    label: "Mobile No",
                },
                {
                    fieldname: "email_id",
                    fieldtype: "Data",
                    label: "Email ID",
                },
                {
                    fieldname: "tax_id",
                    fieldtype: "Data",
                    label: "VAT Registration Number",
                    description: "Optional. Stored as Tax ID on the Supplier.",
                },

                {
                    fieldtype: "Section Break",
                    label: "Address",
                    collapsible: 1,
                },
                {
                    fieldname: "address_type",
                    fieldtype: "Select",
                    label: "Address Type",
                    options: "Billing\nShipping",
                    default: "Billing",
                },
                {
                    fieldname: "address_line1",
                    fieldtype: "Data",
                    label: "Address Line 1",
                },
                {
                    fieldname: "address_line2",
                    fieldtype: "Data",
                    label: "Address Line 2",
                },
                {
                    fieldname: "custom_building_number",
                    fieldtype: "Data",
                    label: "Building Number",
                },
                {
                    fieldname: "custom_area",
                    fieldtype: "Data",
                    label: "Area / District",
                },
                {
                    fieldname: "city",
                    fieldtype: "Data",
                    label: "City / Town",
                },
                {
                    fieldname: "pincode",
                    fieldtype: "Data",
                    label: "Postal Code",
                },
                {
                    fieldname: "country",
                    fieldtype: "Link",
                    options: "Country",
                    label: "Country",
                    default: country,
                },
            ],

            primary_action_label: "Create Supplier",

            primary_action(values) {
                if (values.mobile_no && values.mobile_no.replace(/[^0-9]/g, "").length < 10) {
                    frappe.msgprint("Mobile number must have at least 10 digits.");
                    return;
                }

                frappe.call({
                    method: "rmax_custom.api.supplier.create_supplier_with_address",
                    args: {
                        supplier_name: values.supplier_name,
                        mobile_no: values.mobile_no || null,
                        email_id: values.email_id || null,
                        tax_id: values.tax_id || null,
                        country: values.country || null,
                        address_type: values.address_type || null,
                        address_line1: values.address_line1 || null,
                        address_line2: values.address_line2 || null,
                        custom_building_number: values.custom_building_number || null,
                        custom_area: values.custom_area || null,
                        city: values.city || null,
                        pincode: values.pincode || null,
                    },
                    callback: function (r) {
                        if (r.message) {
                            frm.set_value(supplierField, r.message.supplier);
                            frm.refresh_field(supplierField);
                            frappe.show_alert({
                                message: r.message.message,
                                indicator: "green",
                            });
                            d.hide();
                        }
                    },
                });
            },
        });

        d.show();

        d.fields_dict.mobile_no.$input.on("input", function () {
            let value = this.value.replace(/[^0-9]/g, "");
            if (value.length > 15) value = value.slice(0, 15);
            this.value = value;
        });

        d.fields_dict.pincode.$input.on("input", function () {
            let value = this.value.replace(/[^0-9]/g, "");
            if (value.length > 5) value = value.slice(0, 5);
            this.value = value;
        });
    });
}
