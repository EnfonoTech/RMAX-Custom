// Copyright (c) 2026, Enfono and contributors
// For license information, please see license.txt

frappe.ui.form.on('Warehouse Pick List', {

	onload: function(frm) {
		_setup_wpl_warehouse_query(frm);
	},

	refresh: function(frm) {
		// "Get Items" button — only on draft, with warehouse selected
		if (frm.doc.docstatus === 0 && frm.doc.warehouse) {
			frm.add_custom_button(__('Get Items'), function() {
				_get_pending_items(frm);
			}, __('Actions'));
			frm.change_custom_button_type(__('Get Items'), __('Actions'), 'primary');
		}

		// "Mark as Completed" button — only on submitted Open pick lists
		if (frm.doc.docstatus === 1 && frm.doc.status === 'Open') {
			frm.add_custom_button(__('Mark as Completed'), function() {
				frappe.confirm(
					__('Mark this pick list as completed?'),
					function() {
						frappe.call({
							method: 'rmax_custom.rmax_custom.doctype.warehouse_pick_list.warehouse_pick_list.mark_completed',
							args: { name: frm.doc.name },
							callback: function() {
								frm.reload_doc();
							}
						});
					}
				);
			}, __('Actions'));
		}

		// Color-code rows
		_highlight_pick_rows(frm);
	},

	warehouse: function(frm) {
		// Clear items when warehouse changes
		if (frm.doc.docstatus === 0) {
			frm.clear_table('items');
			frm.clear_table('sources');
			frm.refresh_fields();
		}
	},
});

// ─── Get Pending Items ────────────────────────────────────────

function _get_pending_items(frm) {
	if (!frm.doc.warehouse) {
		frappe.msgprint(__('Please select a Source Warehouse first'));
		return;
	}

	frappe.call({
		method: 'rmax_custom.rmax_custom.doctype.warehouse_pick_list.warehouse_pick_list.get_pending_items',
		args: { warehouse: frm.doc.warehouse },
		freeze: true,
		freeze_message: __('Fetching pending items...'),
		callback: function(r) {
			if (!r.message) return;

			var data = r.message;

			// Clear existing
			frm.clear_table('items');
			frm.clear_table('sources');

			// Populate consolidated items
			(data.items || []).forEach(function(item) {
				var row = frm.add_child('items');
				row.item_code = item.item_code;
				row.item_name = item.item_name;
				row.qty_to_pick = item.qty_to_pick;
				row.available_qty = item.available_qty;
				row.uom = item.uom;
				row.is_urgent = item.is_urgent;
				row.source_documents = item.source_documents;
			});

			// Populate source references
			(data.sources || []).forEach(function(src) {
				var row = frm.add_child('sources');
				row.source_doctype = src.source_doctype;
				row.source_name = src.source_name;
				row.item_code = src.item_code;
				row.item_name = src.item_name;
				row.qty = src.qty;
				row.is_urgent = src.is_urgent;
			});

			frm.refresh_fields();
			frm.dirty();

			// Color-code after render
			setTimeout(function() {
				_highlight_pick_rows(frm);
			}, 300);

			if (data.items && data.items.length) {
				frappe.show_alert({
					message: __('Fetched {0} items to pick', [data.items.length]),
					indicator: 'green'
				});
			}
		}
	});
}

// ─── Highlight Rows ───────────────────────────────────────────

function _highlight_pick_rows(frm) {
	(frm.doc.items || []).forEach(function(item) {
		var $row = frm.fields_dict.items.grid.grid_rows_by_docname[item.name];
		if (!$row || !$row.row) return;

		var needed = flt(item.qty_to_pick);
		var available = flt(item.available_qty);

		if (item.is_urgent) {
			// Urgent — red highlight
			$($row.row).css({
				'border-left': '4px solid #ef4444',
				'background-color': '#fef2f2'
			});
		} else if (needed > 0 && available < needed) {
			// Insufficient stock — orange indicator
			$($row.row).css({
				'border-left': '4px solid #f59e0b',
				'background-color': '#fffbeb'
			});
		} else if (needed > 0 && available >= needed) {
			// Sufficient stock — green
			$($row.row).css({
				'border-left': '4px solid #10b981',
				'background-color': '#f0fdf4'
			});
		} else {
			$($row.row).css({
				'border-left': '',
				'background-color': ''
			});
		}
	});
}

// ─── Warehouse Query ──────────────────────────────────────────

function _setup_wpl_warehouse_query(frm) {
	// Stock users: show their permitted warehouses
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'User Permission',
			filters: {
				user: frappe.session.user,
				allow: 'Warehouse'
			},
			fields: ['for_value'],
			limit_page_length: 0
		},
		async: false,
		callback: function(r) {
			var permitted = (r.message || []).map(function(d) { return d.for_value; });
			frm.set_query('warehouse', function() {
				if (permitted.length) {
					return {
						ignore_user_permissions: 1,
						filters: {
							company: frm.doc.company,
							is_group: 0,
							name: ['in', permitted]
						}
					};
				}
				return {
					filters: {
						company: frm.doc.company,
						is_group: 0
					}
				};
			});
		}
	});
}
