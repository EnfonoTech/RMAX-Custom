/**
 * RMAX Custom: Purchase Invoice Form — auto-negate qty for Debit Notes
 *
 * When is_return=1, any positive qty entered in items is automatically
 * flipped to negative so users don't have to type minus signs.
 */
frappe.ui.form.on("Purchase Invoice Item", {
    qty: function (frm, cdt, cdn) {
        if (!frm.doc.is_return) return;
        var row = frappe.get_doc(cdt, cdn);
        if (row.qty > 0) {
            frappe.model.set_value(cdt, cdn, "qty", -Math.abs(row.qty));
        }
    }
});

frappe.ui.form.on("Purchase Invoice", {
    is_return: function (frm) {
        if (!frm.doc.is_return) return;
        // Negate any existing positive qty rows
        (frm.doc.items || []).forEach(function (row) {
            if (row.qty > 0) {
                frappe.model.set_value(row.doctype, row.name, "qty", -Math.abs(row.qty));
            }
        });
    }
});
