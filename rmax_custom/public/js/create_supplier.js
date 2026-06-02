/**
 * RMAX Custom: Create New Supplier dialog.
 * Registered on Purchase Invoice, Purchase Order, Purchase Receipt.
 *
 * Supplier Kind:
 *   - B2B (Company)   →  Name + Mobile + VAT (15 digits) + full Address mandatory.
 *   - B2C (Individual)→  Name + Mobile required only.
 *   - Branch          →  Name only required, no VAT, no address enforced.
 *
 * Purchase Manager / Purchase Master Manager / System Manager can tick the
 * Allow Duplicate VAT override (B2B only).
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
    const user_roles = frappe.user_roles || [];
    const can_override_vat = user_roles.some((r) => OVERRIDE_ROLES.includes(r));
    const can_set_branch  = user_roles.some((r) => OVERRIDE_ROLES.includes(r));

    frappe.db.get_value("Company", company, ["country", "default_currency"], function (r) {
        const country = r.country;

        const d = new frappe.ui.Dialog({
            title: "Create New Supplier",
            size: "large",

            fields: [
                {
                    fieldname: "buyer_kind",
                    fieldtype: "Select",
                    label: "Supplier Kind",
                    options: can_set_branch
                        ? "B2B (Company)\nB2C (Individual)\nBranch"
                        : "B2B (Company)\nB2C (Individual)",
                    default: "B2B (Company)",
                    reqd: 1,
                    description: "B2B: VAT + Address mandatory. B2C: Name + Mobile only. Branch: Name only, no VAT required.",
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
                    depends_on: "eval:doc.buyer_kind !== 'Branch'",
                    mandatory_depends_on: "eval:doc.buyer_kind !== 'Branch'",
                },
                {
                    fieldname: "email_id",
                    fieldtype: "Data",
                    label: "Email ID",
                },

                // ── B2B-only block ──────────────────────────────────────────
                {
                    fieldtype: "Section Break",
                    label: "B2B Details",
                    depends_on: "eval:doc.buyer_kind === 'B2B (Company)'",
                },
                {
                    fieldname: "tax_id",
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
                    depends_on: "eval:doc.buyer_kind === 'B2B (Company)' && doc.tax_id",
                },
                {
                    fieldname: "duplicate_vat_reason",
                    fieldtype: "Small Text",
                    label: "Duplicate VAT Reason",
                    hidden: can_override_vat ? 0 : 1,
                    depends_on: "eval:doc.allow_duplicate_vat",
                    mandatory_depends_on: "eval:doc.allow_duplicate_vat",
                },

                // ── Address — B2B only, all mandatory ───────────────────────
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

            primary_action_label: "Create Supplier",

            primary_action(values) {
                const is_b2b    = values.buyer_kind === "B2B (Company)";
                const is_branch = values.buyer_kind === "Branch";
                const allow_dup = values.allow_duplicate_vat ? 1 : 0;
                const dup_reason = (values.duplicate_vat_reason || "").trim();
                const vat = (values.tax_id || "").trim();

                // Mobile required for B2B and B2C
                if (!is_branch) {
                    const digits = (values.mobile_no || "").replace(/\D/g, "");
                    if (digits.length < 10) {
                        frappe.msgprint("Mobile number must have at least 10 digits.");
                        return;
                    }
                }

                if (is_b2b) {
                    if (vat.length !== 15) {
                        frappe.msgprint("VAT must be exactly 15 digits.");
                        return;
                    }
                    if ((values.pincode || "").length !== 5) {
                        frappe.msgprint("Postal Code must be exactly 5 digits.");
                        return;
                    }
                }

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

                if (is_b2b && vat && !allow_dup) {
                    frappe.db.get_value("Supplier", { tax_id: vat }, "name").then((res) => {
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
                    const supplier_type = is_branch ? "Branch"
                        : is_b2b ? "Company"
                        : "Individual";

                    frappe.call({
                        method: "rmax_custom.api.supplier.create_supplier_with_address",
                        args: {
                            supplier_name:          values.supplier_name,
                            mobile_no:              is_branch ? null : (values.mobile_no || null),
                            email_id:               values.email_id || null,
                            supplier_type:          supplier_type,
                            buyer_kind:             values.buyer_kind,
                            tax_id:                 is_b2b ? (vat || null) : null,
                            address_type:           is_b2b ? values.address_type : null,
                            address_line1:          is_b2b ? values.address_line1 : null,
                            address_line2:          is_b2b ? (values.address_line2 || null) : null,
                            custom_building_number: is_b2b ? values.custom_building_number : null,
                            custom_area:            is_b2b ? values.custom_area : null,
                            pincode:                is_b2b ? values.pincode : null,
                            city:                   is_b2b ? values.city : null,
                            country:                is_b2b ? values.country : null,
                            allow_duplicate_vat:    allow_dup,
                            duplicate_vat_reason:   allow_dup ? dup_reason : null,
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

        // Digit-only masks
        d.fields_dict.mobile_no.$input.on("input", function () {
            let value = this.value.replace(/[^0-9]/g, "");
            if (value.length > 15) value = value.slice(0, 15);
            this.value = value;
        });

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
    });
}
