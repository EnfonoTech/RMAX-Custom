// Copyright (c) 2026, Enfono and contributors
// For license information, please see license.txt

frappe.ui.form.on('Damage Slip', {
	onload: function(frm) {
		_setup_ds_warehouse_query(frm);
	},

	refresh: function(frm) {
		// Show status indicator
		if (frm.doc.status === 'Transferred') {
			frm.set_intro(__('This Damage Slip has been transferred via {0}.',
				['<a href="/app/damage-transfer/' + frm.doc.damage_transfer + '">' +
				 frm.doc.damage_transfer + '</a>']
			), 'green');
			frm.disable_save();
		}

		// Make fields read-only if transferred
		if (frm.doc.status === 'Transferred') {
			frm.set_read_only();
		}
	},

	customer: function(frm) {
		// If customer is set, suggest it's a customer return
		if (frm.doc.customer && !frm.doc.reference_doctype) {
			frm.set_value('reference_doctype', 'Sales Invoice');
		}
	},

	reference_doctype: function(frm) {
		frm.set_value('reference_document', '');
		if (frm.doc.reference_doctype === 'Sales Invoice') {
			frm.set_query('reference_document', function() {
				return {
					filters: {
						docstatus: 1,
						customer: frm.doc.customer || undefined,
						company: frm.doc.company,
					}
				};
			});
		} else if (frm.doc.reference_doctype === 'Delivery Note') {
			frm.set_query('reference_document', function() {
				return {
					filters: {
						docstatus: 1,
						customer: frm.doc.customer || undefined,
						company: frm.doc.company,
					}
				};
			});
		}
	}
});

function _setup_ds_warehouse_query(frm) {
	// Branch warehouse: only user's permitted warehouses
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "User Permission",
			filters: { user: frappe.session.user, allow: "Warehouse" },
			fields: ["for_value"],
			limit_page_length: 0
		},
		callback: function(r) {
			var permitted = (r.message || []).map(function(d) { return d.for_value; });
			frm.set_query('branch_warehouse', function() {
				if (permitted.length) {
					return {
						ignore_user_permissions: 1,
						filters: { company: frm.doc.company, is_group: 0, name: ["in", permitted] }
					};
				}
				return { filters: { company: frm.doc.company, is_group: 0 } };
			});
		}
	});
}
