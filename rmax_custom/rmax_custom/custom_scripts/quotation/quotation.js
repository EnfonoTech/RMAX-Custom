frappe.ui.form.on('Quotation', {
    refresh(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button('Sales Invoice', () => {
                frappe.model.open_mapped_doc({
                    method: "erpnext.selling.doctype.quotation.quotation.make_sales_invoice",
                    frm: frm
                });
            }, 'Create');
        }
    }
});