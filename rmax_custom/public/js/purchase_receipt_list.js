frappe.listview_settings['Purchase Receipt'] = {
    onload: function(listview) {
        listview.page.add_action_item(__('Create Single Purchase Invoice'), function() {
            let selected = listview.get_checked_items();
            if (selected.length === 0) {
                frappe.msgprint(__('Please select at least one Purchase Receipt.'));
                return;
            }

            let receipt_names = selected.map(r => r.name);

            frappe.confirm(
                __('Create 1 Purchase Invoice from ' + receipt_names.length + ' Purchase Receipt(s)?'),
                function() {
                    frappe.call({
                        method: 'rmax_custom.api.purchase_invoice.create_single_purchase_invoice',
                        args: {
                            receipt_names: receipt_names
                        },
                        freeze: true,
                        freeze_message: __('Creating Purchase Invoice...'),
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: __('Success'),
                                    message: __('Purchase Invoice <a href="/app/purchase-invoice/' + r.message + '">' + r.message + '</a> created successfully.'),
                                    indicator: 'green'
                                });
                                listview.refresh();
                            }
                        }
                    });
                }
            );
        });
    }
};
