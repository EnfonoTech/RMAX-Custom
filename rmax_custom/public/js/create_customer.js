/**
 * RMAX Custom: Create New Customer dialog (Sales Invoice).
 *
 * Customer split:
 *   - B2C (Individual)  →  only Customer Name + Mobile No required.
 *   - B2B (Company)     →  Customer Name + Mobile No + VAT (15 digits) +
 *                          full Address block all mandatory.
 *
 * Sales Manager / Sales Master Manager / System Manager can tick the
 * Allow Duplicate VAT override (B2B only).
 */

frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        add_create_customer_button(frm);
    },
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
    const company = frm.doc.company || frappe.defaults.get_default("company");

    const OVERRIDE_ROLES = ["Sales Manager", "Sales Master Manager", "System Manager"];
    const can_override_vat = (frappe.user_roles || []).some((r) =>
        OVERRIDE_ROLES.includes(r)
    );

    frappe.db.get_value(
        "Company",
        company,
        ["country", "default_currency"],
        function (r) {
            const country = r.country;
            const default_currency = r.default_currency;

            const d = new frappe.ui.Dialog({
                title: "Create New Customer",
                size: "large",

                fields: [
                    {
                        fieldname: "buyer_kind",
                        fieldtype: "Select",
                        label: "Customer Kind",
                        options: "B2C (Individual)\nB2B (Company)",
                        default: "B2C (Individual)",
                        reqd: 1,
                        description: "B2C: only Name + Mobile required. B2B: VAT + Address mandatory.",
                    },

                    { fieldtype: "Section Break" },

                    {
                        fieldname: "customer_name",
                        fieldtype: "Data",
                        label: "Customer Name",
                        reqd: 1,
                    },
                    {
                        fieldname: "custom_customer_name_ar",
                        label: __("Customer Name (Arabic)"),
                        fieldtype: "Data",
                        description: __("Optional. Renders on bilingual ZATCA print format and enables Arabic search."),
                        reqd: 0,
                    },
                    {
                        fieldname: "mobile_no",
                        fieldtype: "Data",
                        label: "Mobile No",
                        reqd: 1,
                    },
                    {
                        fieldname: "email_id",
                        fieldtype: "Data",
                        label: "Email ID",
                    },

                    // ---- B2B-only block ----
                    {
                        fieldtype: "Section Break",
                        label: "B2B Details",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "custom_vat_registration_number",
                        fieldtype: "Data",
                        label: "VAT Registration Number",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        mandatory_depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        description: "Exactly 15 digits.",
                    },
                    {
                        fieldname: "allow_duplicate_vat",
                        fieldtype: "Check",
                        label: "Allow Duplicate VAT (Manager Override)",
                        default: 0,
                        hidden: can_override_vat ? 0 : 1,
                        depends_on:
                            "eval:doc.buyer_kind === 'B2B (Company)' && doc.custom_vat_registration_number",
                    },
                    {
                        fieldname: "duplicate_vat_reason",
                        fieldtype: "Small Text",
                        label: "Duplicate VAT Reason",
                        hidden: can_override_vat ? 0 : 1,
                        depends_on: "eval:doc.allow_duplicate_vat",
                        mandatory_depends_on: "eval:doc.allow_duplicate_vat",
                    },

                    {
                        fieldtype: "Section Break",
                        label: "Address Details",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "address_type",
                        fieldtype: "Select",
                        label: "Address Type",
                        options: "Billing\nShipping",
                        default: "Billing",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        mandatory_depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "address_line1",
                        fieldtype: "Data",
                        label: "Address Line 1",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        mandatory_depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "address_line2",
                        fieldtype: "Data",
                        label: "Address Line 2",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "custom_building_number",
                        fieldtype: "Data",
                        label: "Building Number",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        mandatory_depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "custom_area",
                        fieldtype: "Data",
                        label: "Area/District",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        mandatory_depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "city",
                        fieldtype: "Data",
                        label: "City/Town",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        mandatory_depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "country",
                        fieldtype: "Link",
                        options: "Country",
                        label: "Country",
                        default: country,
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        mandatory_depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                    {
                        fieldname: "pincode",
                        fieldtype: "Data",
                        label: "Postal Code",
                        depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                        mandatory_depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                    },
                ],

                primary_action_label: "Create Customer",

                primary_action(values) {
                    const is_b2b = values.buyer_kind === "B2B (Company)";

                    const mobile = values.mobile_no || "";
                    if (mobile.length < 10) {
                        frappe.msgprint("Mobile number must have at least 10 digits.");
                        return;
                    }

                    const allow_dup = values.allow_duplicate_vat ? 1 : 0;
                    const dup_reason = (values.duplicate_vat_reason || "").trim();

                    if (allow_dup && !can_override_vat) {
                        frappe.msgprint(
                            "You do not have permission to override the VAT duplicate check. Required role: Sales Manager."
                        );
                        return;
                    }
                    if (allow_dup && !dup_reason) {
                        frappe.msgprint("Please provide the Duplicate VAT Reason.");
                        return;
                    }

                    if (is_b2b) {
                        const vat = values.custom_vat_registration_number || "";
                        if (vat.length !== 15) {
                            frappe.msgprint("VAT must be exactly 15 digits.");
                            return;
                        }
                        const pincode = values.pincode || "";
                        if (pincode.length !== 5) {
                            frappe.msgprint("Postal Code must be exactly 5 digits.");
                            return;
                        }

                        if (!allow_dup) {
                            // Pre-check duplicate VAT before submit
                            frappe.db
                                .get_value("Customer", { custom_vat_registration_number: vat }, "name")
                                .then((res) => {
                                    if (res.message && res.message.name) {
                                        frappe.msgprint(
                                            `VAT already exists for Customer: ${res.message.name}. A Sales Manager can tick 'Allow Duplicate VAT' to override.`
                                        );
                                        return;
                                    }
                                    submit_create();
                                });
                            return;
                        }
                    }

                    submit_create();

                    function submit_create() {
                        const customer_type = is_b2b ? "Company" : "Individual";
                        frappe.call({
                            method: "rmax_custom.api.customer.create_customer_with_address",
                            args: {
                                customer_name: values.customer_name,
                                custom_customer_name_ar: values.custom_customer_name_ar || "",
                                mobile_no: values.mobile_no,
                                email_id: values.email_id || null,
                                customer_type: customer_type,
                                buyer_kind: values.buyer_kind,
                                custom_vat_registration_number: is_b2b
                                    ? values.custom_vat_registration_number || null
                                    : null,
                                address_type: is_b2b ? values.address_type : null,
                                address_line1: is_b2b ? values.address_line1 : null,
                                address_line2: is_b2b ? values.address_line2 || null : null,
                                custom_building_number: is_b2b
                                    ? values.custom_building_number
                                    : null,
                                custom_area: is_b2b ? values.custom_area : null,
                                pincode: is_b2b ? values.pincode : null,
                                city: is_b2b ? values.city : null,
                                country: is_b2b ? values.country : null,
                                default_currency: default_currency,
                                allow_duplicate_vat: allow_dup,
                                duplicate_vat_reason: allow_dup ? dup_reason : null,
                            },
                            callback: function (r) {
                                if (r.message) {
                                    frm.set_value("customer", r.message.customer);
                                    frm.refresh_field("customer");
                                    frappe.show_alert({
                                        message: r.message.message,
                                        indicator: "green",
                                    });
                                    d.hide();
                                }
                            },
                        });
                    }
                },
            });

            d.show();

            // Live digit-only masks
            d.fields_dict.mobile_no.$input.on("input", function () {
                let value = this.value.replace(/[^0-9]/g, "");
                if (value.length > 15) value = value.slice(0, 15);
                this.value = value;
            });

            d.fields_dict.custom_vat_registration_number.$input.on("input", function () {
                let value = this.value.replace(/[^0-9]/g, "");
                if (value.length > 15) value = value.slice(0, 15);
                this.value = value;
            });

            d.fields_dict.pincode.$input.on("input", function () {
                let value = this.value.replace(/[^0-9]/g, "");
                if (value.length > 5) value = value.slice(0, 5);
                this.value = value;
            });
        }
    );
}
