frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        add_create_customer_button(frm); 
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
            size: "large",

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
                    fieldname: "customer_type",
                    fieldtype: "Select",
                    label: "Customer Type",
                    options: "Company\nIndividual\nPartnership\nBranch",
                    default: "Company"
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
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number"
                },
                {
                    fieldname: "address_line1",
                    fieldtype: "Data",
                    label: "Address Line 1",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number"
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
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number"
                },
                {
                    fieldname: "custom_area",
                    fieldtype: "Data",
                    label: "Area/District",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number"
                },
                {
                    fieldname: "city",
                    fieldtype: "Data",
                    label: "City/Town",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number"
                },
                {
                    fieldname: "country",
                    fieldtype: "Link",
                    options: "Country",
                    label: "Country",
                    default: country,
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number"
                },
                {
                    fieldname: "pincode",
                    fieldtype: "Data",
                    label: "Postal Code",
                    mandatory_depends_on: "eval:doc.custom_vat_registration_number"
                }
            ],

            primary_action_label: "Create Customer",

            primary_action(values) {

                let mobile = values.mobile_no || "";

                if (mobile.length < 10) {
                    frappe.msgprint("Mobile number must have at least 10 digits.");
                    return;
                }
                let vat = values.custom_vat_registration_number;
                let type = values.customer_type;
                if (vat && vat.length !== 15) {
                    frappe.msgprint("VAT must be exactly 15 digits.");
                    return;
                }
                let pincode = values.pincode || "";
                if (pincode && pincode.length !== 5) {
                    frappe.msgprint("Pincode must be exactly 5 digits.");
                    return;
                }
                if (vat && type !== "Branch") {
                    frappe.db.get_value("Customer", {
                        custom_vat_registration_number: vat
                    }, "name").then(r => {
                        if (r.message && r.message.name) {
                            frappe.msgprint(
                                `VAT already exists for Customer: ${r.message.name}`
                            );
                            return;
                        }
                        create_customer();
                    });

                    return;
                }
                create_customer();
                function create_customer() {
                    frappe.call({
                        method: "rmax_custom.api.customer.create_customer_with_address",
                        args: {
                            customer_name: values.customer_name,
                            mobile_no: values.mobile_no,
                            email_id: values.email_id || null,
                            customer_type: values.customer_type,
                            address_type: values.address_type,
                            address_line1: values.address_line1,
                            address_line2: values.address_line2 || null,
                            custom_vat_registration_number: vat || null,
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
            }
        });

        d.show();
        d.fields_dict.mobile_no.$input.on("input", function () {
            this.value = this.value.replace(/[^0-9]/g, '');
        });

        d.fields_dict.custom_vat_registration_number.$input.on("input", function () {
            let value = this.value.replace(/[^0-9]/g, '');
            if (value.length > 15) {
                value = value.slice(0, 15);
            }
            this.value = value;
        });

    });
}