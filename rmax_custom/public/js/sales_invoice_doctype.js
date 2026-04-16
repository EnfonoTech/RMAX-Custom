/**
 * RMAX Custom: Sales Invoice Form — auto-negate qty for Credit Notes
 *
 * When is_return=1, any positive qty is flipped to negative on save
 * so users don't have to type minus signs.
 */
frappe.ui.form.on("Sales Invoice", {
    before_save: function (frm) {
        if (!frm.doc.is_return) return;
        (frm.doc.items || []).forEach(function (row) {
            if (row.qty > 0) {
                frappe.model.set_value(row.doctype, row.name, "qty", -Math.abs(row.qty));
            }
        });
    }
});
