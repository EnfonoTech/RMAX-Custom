frappe.ui.form.on('Contact', {
    validate: function(frm) {
        function count_digits(val) {
            return (val || "").replace(/\D/g, "").length;
        }

        (frm.doc.phone_nos || []).forEach(row => {

            if (row.phone && count_digits(row.phone) < 10) {
                frappe.throw("Mobile number must have at least 10 digits.");

            }

        });
    }
});