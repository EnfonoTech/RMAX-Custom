/**
 * RMAX Custom: Create New Supplier dialog.
 * Registered on Purchase Invoice, Purchase Order, Purchase Receipt.
 *
 * Only Supplier Name is mandatory. VAT (tax_id) and Address are optional
 * and visible for both B2C and B2B. Supplier Kind only controls supplier_type.
 *
 * Purchase Manager / Purchase Master Manager / System Manager can tick the
 * Allow Duplicate VAT override when a duplicate tax_id is detected.
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
        if (opts.preAction) opts.preAction();
        open_create_supplier_dialog(frm, opts);
    });
    $field.before($btn);
}

function open_create_supplier_dialog(frm, opts) {
    opts = opts || {};
    const supplierField = opts.supplierField || "supplier";
    const company = frm.doc.company || frappe.defaults.get_default("company");

    const OVERRIDE_ROLES = ["Purchase Manager", "Purchase Master Manager", "System Manager"];
    const can_override_vat = (frappe.user_roles || []).some((r) =>
        OVERRIDE_ROLES.includes(r)
    );

    frappe.db.get_value(
        "Company",
        company,
        ["country", "default_currency"],
        function (r) {
            const country = r.country;

            const d = new frappe.ui.Dialog({
                title: "Create New Supplier",
                size: "large",

                fields: [
                    {
                        fieldname: "buyer_kind",
                        fieldtype: "Select",
                        label: "Supplier Kind",
                        options: "B2C (Individual)\nB2B (Company)",
                        default: "B2B (Company)",
                        reqd: 1,
                        description: "Sets the Supplier Type. Does not affect which fields are required.",
                    },

                    { fieldtype: "Section Break" },

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
                        description: "Optional. Exactly 15 digits if provided.",
                    },
                    {
                        fieldname: "allow_duplicate_vat",
                        fieldtype: "Check",
                        label: "Allow Duplicate VAT (Manager Override)",
                        default: 0,
                        hidden: can_override_vat ? 0 : 1,
                        depends_on: "eval:doc.tax_id",
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
                        label: "Area/District",
                    },
                    {
                        fieldname: "city",
                        fieldtype: "Data",
                        label: "City/Town",
                    },
                    {
                        fieldname: "country",
                        fieldtype: "Link",
                        options: "Country",
                        label: "Country",
                        default: country,
                    },
                    {
                        fieldname: "pincode",
                        fieldtype: "Data",
                        label: "Postal Code",
                    },
                ],

                primary_action_label: "Create Supplier",

                primary_action(values) {
                    const allow_dup = values.allow_duplicate_vat ? 1 : 0;
                    const dup_reason = (values.duplicate_vat_reason || "").trim();
                    const vat = (values.tax_id || "").trim();

                    if (allow_dup && !can_override_vat) {
                        frappe.msgprint(
                            "You do not have permission to override the VAT duplicate check. Required role: Purchase Manager."
                        );
                        return;
                    }
                    if (allow_dup && !dup_reason) {
                        frappe.msgprint("Please provide the Duplicate VAT Reason.");
                        return;
                    }

                    if (vat && vat.length !== 15) {
                        frappe.msgprint("VAT must be exactly 15 digits.");
                        return;
                    }

                    if (vat && !allow_dup) {
                        frappe.db
                            .get_value("Supplier", { tax_id: vat }, "name")
                            .then((res) => {
                                if (res.message && res.message.name) {
                                    frappe.msgprint(
                                        `VAT already exists for Supplier: ${res.message.name}. A Purchase Manager can tick 'Allow Duplicate VAT' to override.`
                                    );
                                    return;
                                }
                                submit_create();
                            });
                        return;
                    }

                    submit_create();

                    function submit_create() {
                        const supplier_type = values.buyer_kind === "B2B (Company)" ? "Company" : "Individual";
                        frappe.call({
                            method: "rmax_custom.api.supplier.create_supplier_with_address",
                            args: {
                                supplier_name: values.supplier_name,
                                mobile_no: values.mobile_no || null,
                                email_id: values.email_id || null,
                                supplier_type: supplier_type,
                                buyer_kind: values.buyer_kind,
                                tax_id: vat || null,
                                address_type: values.address_type || null,
                                address_line1: values.address_line1 || null,
                                address_line2: values.address_line2 || null,
                                custom_building_number: values.custom_building_number || null,
                                custom_area: values.custom_area || null,
                                pincode: values.pincode || null,
                                city: values.city || null,
                                country: values.country || null,
                                allow_duplicate_vat: allow_dup,
                                duplicate_vat_reason: allow_dup ? dup_reason : null,
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
                    }
                },
            });

            d.show();

            d.fields_dict.tax_id.$input.on("input", function () {
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
