
frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        add_create_customer_button(frm); 
        console.log("Sales Invoice Custom Script Loaded");
	}
});

function add_create_customer_button(frm) {

    if (frm.doc.docstatus !== 0) return;
    if (!frm.fields_dict.customer) return;

    const $field = frm.fields_dict.customer.$wrapper;
    const $parent = $field.parent();

    if ($parent.find(".create-customer-btn").length) return;

    const $btn = $(`
        <button type="button"
            class="btn btn-sm btn-secondary create-customer-btn"
            style="margin-bottom: 5px;">
            <i class="fa fa-plus"></i> Create New Customer
        </button>
    `);

    $btn.on("click", function () {
        open_create_customer_dialog(frm);
    });

    $field.before($btn);
}


function open_create_customer_dialog(frm) {

    let company = frm.doc.company || frappe.defaults.get_default("company");

    frappe.db.get_value("Company", company,
        ["country", "default_currency"], function(r) {

        let country = r.country;
        let default_currency = r.default_currency;

        let d = new frappe.ui.Dialog({
            title: "Create New Customer",
            size: "large",   // important when many fields

            fields: [
                {
                    fieldname: "customer_name",
                    fieldtype: "Data",
                    label: "Customer Name",
                    reqd: 1
                },
                {
                    fieldname: "mobile_no",
                    fieldtype: "Data",
                    label: "Mobile No",
                    reqd: 1
                },
                {
                    fieldname: "email_id",
                    fieldtype: "Data",
                    label: "Email ID"
                },
                { 
                    fieldname: "custom_vat_registration_number",
                    fieldtype: "Data",
                    label: "VAT Registration Number"
                },
                { fieldtype: "Section Break", label: "Address Details" },
                {
                    fieldname: "address_type",
                    fieldtype: "Select",
                    label: "Address Type",
                    options: "Billing\nShipping",
                    default: "Billing",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number",
                },
                {
                    fieldname: "address_line1",
                    fieldtype: "Data",
                    label: "Address Line 1",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number",
                },
                {
                    fieldname: "address_line2",
                    fieldtype: "Data",
                    label: "Address Line 2"
                },
                {
                    fieldname: "custom_building_number",
                    fieldtype: "Data",
                    label: "Building Number",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number",
                },
                {
                    fieldname: "custom_area",
                    fieldtype: "Data",
                    label: "Area/District",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number ",
                },
                {
                    fieldname: "city",
                    fieldtype: "Data",
                    label: "City/Town",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number",
                },
                {
                    fieldname: "country",
                    fieldtype: "Link",
                    options: "Country",
                    label: "Country",
                    default: country,
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number",
                },
                {
                    fieldname: "pincode",
                    fieldtype: "Data",
                    label: "Postal Code",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number",
                },

            ],
            primary_action_label: "Create Customer",
            primary_action(values) {
                function count_digits(val) {
                    if (!val) return 0;
                    return val.replace(/\D/g, "").length;
                }
                if (count_digits(values.mobile_no) < 10) {
                    frappe.throw("Mobile number must have at least 10 digits.");
                        }
                frappe.call({
                    method: "rmax_custom.api.customer.create_customer_with_address",
                    args: {
                        customer_name: values.customer_name,
                        mobile_no: values.mobile_no,
                        email_id: values.email_id || null,
                        address_type: values.address_type, 
                        address_line1: values.address_line1,
                        address_line2: values.address_line2 || null,
                        custom_vat_registration_number: values.custom_vat_registration_number || null,
                        custom_building_number: values.custom_building_number,
                        custom_area: values.custom_area,
                        pincode: values.pincode,
                        city: values.city,  
                        country: values.country,
                        default_currency: default_currency
                    },
                    callback: function(r) {
                        if (r.message) {

                            frm.set_value("customer", r.message.customer);
                            frm.refresh_field("customer");

                            frappe.show_alert({
                                message: r.message.message,
                                indicator: "green"
                            });

                            d.hide();
                        }
                    }
                });
            }
        });

        d.show();
    });
}

