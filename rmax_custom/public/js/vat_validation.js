frappe.ui.form.on('Customer', {
    refresh: function(frm) {
        let field = frm.get_field('custom_vat_registration_number');
        if (field && field.$input) {
            field.$input.off('input').on('input', function() {
                let value = this.value;
                value = value.replace(/\D/g, '');
                if (value.length > 15) {
                    frappe.msgprint("Maximum 15 digits allowed");
                    value = value.slice(0, 15);
                }
                this.value = value;
                frm.set_value('custom_vat_registration_number', value);
            });
        }
        set_customer_type_filter(frm);
    },

//    validate: async function(frm) {

//     let vat = frm.doc.custom_vat_registration_number;

//     // ---------------- VAT VALIDATION ----------------
//     if (vat) {
//         if (vat.length > 15) {
//             frappe.throw("VAT cannot exceed 15 digits");
//         }

//         await frappe.call({
//             method: "rmax_custom.api.customer.validate_vat_customer",
//             args: {
//                 vat: vat,
//                 customer_type: frm.doc.customer_type,
//                 name: frm.doc.name || null
//             }
//         });
//     }

//     if (frm.doc.customer_primary_contact) {

//         let r = await frappe.call({
//             method: "frappe.client.get",
//             args: {
//                 doctype: "Contact",
//                 name: frm.doc.customer_primary_contact
//             }
//         });

//         let contact = r.message;

//         function count_digits(val) {
//             if (!val) return 0;
//             return val.replace(/\D/g, "").length;
//         }

//         (contact.phone_nos || []).forEach(row => {

//             if (row.phone && count_digits(row.phone) < 10) {

//                 if (row.is_primary_mobile) {
//                     frappe.throw("Mobile number must have at least 10 digits.");
//                 } else {
//                     frappe.throw("Phone number must have at least 10 digits.");
//                 }

//             }

//         });
//     }
validate: async function(frm) {

    let vat = frm.doc.custom_vat_registration_number;
    if (vat && vat.length !== 15) {
        frappe.throw("VAT must be exactly 15 digits");
    }
    if (vat) {
        await frappe.call({
            method: "rmax_custom.api.customer.validate_vat_customer",
            args: {
                vat: vat,
                customer_type: frm.doc.customer_type,
                name: frm.doc.name || null
            }
        });
    }
    if (frm.doc.customer_primary_contact) {

        let r = await frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Contact",
                name: frm.doc.customer_primary_contact
            }
        });

        let contact = r.message;

        function count_digits(val) {
            if (!val) return 0;
            return val.replace(/\D/g, "").length;
        }

        for (let row of (contact.phone_nos || [])) {

            if (row.phone && count_digits(row.phone) < 10) {

                if (row.is_primary_mobile) {
                    frappe.throw("Mobile number must have at least 10 digits.");
                } else {
                    frappe.throw("Phone number must have at least 10 digits.");
                }
            }
        }
    }
},
    onload: function(frm) {
        set_customer_type_filter(frm);
    }
});


function set_customer_type_filter(frm) {
    let allowed_roles = ["System Manager", "Auditor"];
    let user_roles = frappe.user_roles || [];

    let is_allowed = allowed_roles.some(role => user_roles.includes(role));

    let field = frm.get_field("customer_type");
    if (!field) return;

    let options = (field.df.options || "").split("\n");

    if (!is_allowed) {
        options = options.filter(opt => opt.trim() !== "Branch");

        field.df.options = options.join("\n");
        frm.refresh_field("customer_type");

        console.log("Branch removedss from Customer Type");
    }
}