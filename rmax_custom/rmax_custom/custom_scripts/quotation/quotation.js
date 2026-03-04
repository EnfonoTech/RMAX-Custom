frappe.ui.form.on('Quotation', {
    refresh(frm) {
        setTimeout(() => {
            frm.remove_custom_button(__('Sales Order'), __('Create'));
        }, 10);
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