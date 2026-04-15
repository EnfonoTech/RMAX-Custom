// Copyright (c) 2026, Enfono and contributors
// For license information, please see license.txt

frappe.ui.form.on('Damage Transfer', {
	onload: function(frm) {
		_setup_dt_warehouse_query(frm);
	},

	refresh: function(frm) {
		// === "Get Damage Slips" button -- Draft state ===
		if (frm.doc.docstatus === 0 && frm.doc.workflow_state === 'Draft') {
			if (frm.doc.branch_warehouse && frm.doc.company) {
				frm.add_custom_button(__('Get Damage Slips'), function() {
					_get_damage_slips_dialog(frm);
				});
			}
		}

		// === "Write Off" button -- after Approved, before Written Off ===
		if (frm.doc.docstatus === 1
			&& frm.doc.workflow_state === 'Approved'
			&& !frm.doc.writeoff_entry_created) {
			frm.add_custom_button(__('Write Off'), function() {
				frappe.confirm(
					__('This will create a Material Issue Stock Entry to write off all items. Proceed?'),
					function() {
						frappe.call({
							method: 'rmax_custom.rmax_custom.doctype.damage_transfer.damage_transfer.write_off_damage',
							args: { damage_transfer_name: frm.doc.name },
							freeze: true,
							freeze_message: __('Creating Write-Off Entry...'),
							callback: function(r) {
								frm.reload_doc();
							}
						});
					}
				);
			}, __('Actions'));
		}

		// === Status indicators ===
		if (frm.doc.workflow_state === 'Written Off') {
			frm.set_intro(__('This Damage Transfer has been written off.'), 'blue');
		}

		// === Field visibility per state ===
		_toggle_inspection_fields(frm);

		// === Show warning for items without Damage Slip reference ===
		_show_showroom_damage_warning(frm);
	},

	branch_warehouse: function(frm) {
		// Auto-set company from warehouse if not set
		if (frm.doc.branch_warehouse && !frm.doc.company) {
			frappe.db.get_value('Warehouse', frm.doc.branch_warehouse, 'company', function(r) {
				if (r && r.company) {
					frm.set_value('company', r.company);
				}
			});
		}
	}
});

function _toggle_inspection_fields(frm) {
	// Inspection fields (supplier_code, images, remarks on items) should be:
	// - Hidden in Draft state (Branch User fills items only)
	// - Editable in Pending Inspection state (Damage User inspects)
	// - Read-only in Approved/Written Off state
	var state = frm.doc.workflow_state;
	var is_readonly = (state === 'Approved' || state === 'Written Off');

	// Use grid field properties
	var grid = frm.fields_dict.items.grid;
	if (grid) {
		grid.toggle_display('supplier_code', state !== 'Draft');
		grid.toggle_display('images', state !== 'Draft');
		grid.toggle_display('image_2', state !== 'Draft');
		grid.toggle_display('image_3', state !== 'Draft');
		grid.toggle_display('remarks', state !== 'Draft');

		// In approved/written-off, everything read-only
		if (is_readonly) {
			frm.set_read_only();
		}
	}
}

function _show_showroom_damage_warning(frm) {
	if (frm.doc.docstatus !== 0) return;
	var has_unlinked = false;
	(frm.doc.items || []).forEach(function(item) {
		if (!item.damage_slip) {
			has_unlinked = true;
		}
	});
	if (has_unlinked) {
		frm.dashboard.set_headline(
			__('Warning: Items without a Damage Slip reference will be treated as Showroom Damage.'),
			'orange'
		);
	}
}

function _get_damage_slips_dialog(frm) {
	frappe.call({
		method: 'rmax_custom.rmax_custom.doctype.damage_transfer.damage_transfer.get_pending_damage_slips',
		args: {
			branch_warehouse: frm.doc.branch_warehouse,
			company: frm.doc.company,
		},
		freeze: true,
		callback: function(r) {
			if (!r.message || !r.message.length) {
				frappe.msgprint(__('No pending Damage Slips found for this branch.'));
				return;
			}

			var slips = r.message;
			var d = new frappe.ui.Dialog({
				title: __('Select Damage Slips'),
				size: 'large',
				fields: [
					{
						fieldtype: 'HTML',
						fieldname: 'slip_list',
					}
				],
				primary_action_label: __('Add Selected'),
				primary_action: function() {
					var selected = [];
					d.$wrapper.find('input.slip-check:checked').each(function() {
						var idx = $(this).data('idx');
						selected.push(slips[idx]);
					});

					if (!selected.length) {
						frappe.msgprint(__('Please select at least one Damage Slip.'));
						return;
					}

					_add_slips_to_transfer(frm, selected);
					d.hide();
				}
			});

			// Build HTML table
			var html = '<table class="table table-bordered table-hover">';
			html += '<thead><tr>';
			html += '<th><input type="checkbox" class="slip-check-all"></th>';
			html += '<th>Slip</th><th>Date</th><th>Category</th>';
			html += '<th>Items</th><th>Total Qty</th><th>Customer</th>';
			html += '</tr></thead><tbody>';

			slips.forEach(function(slip, i) {
				html += '<tr>';
				html += '<td><input type="checkbox" class="slip-check" data-idx="' + i + '"></td>';
				html += '<td><a href="/app/damage-slip/' + slip.name + '" target="_blank">' + slip.name + '</a></td>';
				html += '<td>' + frappe.datetime.str_to_user(slip.date) + '</td>';
				html += '<td>' + (slip.damage_category || '') + '</td>';
				html += '<td>' + slip.total_items + '</td>';
				html += '<td>' + slip.total_qty + '</td>';
				html += '<td>' + (slip.customer || '-') + '</td>';
				html += '</tr>';
			});

			html += '</tbody></table>';
			d.fields_dict.slip_list.$wrapper.html(html);

			// Select all checkbox
			d.$wrapper.find('.slip-check-all').on('change', function() {
				var checked = $(this).is(':checked');
				d.$wrapper.find('.slip-check').prop('checked', checked);
			});

			d.show();
		}
	});
}

function _add_slips_to_transfer(frm, selected_slips) {
	// Track existing slip names to avoid duplicates
	var existing_slips = {};
	(frm.doc.damage_slips || []).forEach(function(row) {
		existing_slips[row.damage_slip] = true;
	});

	selected_slips.forEach(function(slip) {
		if (existing_slips[slip.name]) return; // skip duplicate

		// Add to damage_slips child table
		frm.add_child('damage_slips', {
			damage_slip: slip.name,
			slip_date: slip.date,
			damage_category: slip.damage_category,
			total_items: slip.total_items,
		});

		// Add items to items child table
		(slip.items || []).forEach(function(item) {
			// Check if item already exists from same slip (consolidate qty)
			var found = false;
			(frm.doc.items || []).forEach(function(existing) {
				if (existing.item_code === item.item_code && existing.damage_slip === slip.name) {
					existing.qty = flt(existing.qty) + flt(item.qty);
					found = true;
				}
			});

			if (!found) {
				frm.add_child('items', {
					item_code: item.item_code,
					item_name: item.item_name,
					qty: item.qty,
					stock_uom: item.stock_uom,
					damage_category: slip.damage_category,
					damage_slip: slip.name,
				});
			}
		});
	});

	frm.refresh_field('damage_slips');
	frm.refresh_field('items');
	frm.dirty();
	frappe.show_alert({ message: __('Damage Slips added.'), indicator: 'green' });
}

function _setup_dt_warehouse_query(frm) {
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

	// Supplier Code query -- only enabled supplier codes
	frm.set_query('supplier_code', 'items', function() {
		return { filters: { enabled: 1 } };
	});
}
