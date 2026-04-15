// Copyright (c) 2026, Enfono and contributors
// For license information, please see license.txt

frappe.ui.form.on('Warehouse Pick List', {

	onload: function(frm) {
		_setup_wpl_warehouse_query(frm);
	},

	refresh: function(frm) {
		// Manual selection buttons — only on draft, with warehouse selected
		if (frm.doc.docstatus === 0 && frm.doc.warehouse) {
			frm.add_custom_button(__('Add Material Request'), function() {
				_show_mr_selection(frm);
			}, __('Get Items'));

			frm.add_custom_button(__('Add Stock Transfer'), function() {
				_show_st_selection(frm);
			}, __('Get Items'));
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

// ─── Show Material Request Selection Dialog ──────────────────

function _show_mr_selection(frm) {
	if (!frm.doc.warehouse) {
		frappe.msgprint(__('Please select a Source Warehouse first'));
		return;
	}

	frappe.call({
		method: 'rmax_custom.rmax_custom.doctype.warehouse_pick_list.warehouse_pick_list.get_pending_material_requests',
		args: { warehouse: frm.doc.warehouse },
		freeze: true,
		freeze_message: __('Loading pending Material Requests...'),
		callback: function(r) {
			var mrs = r.message || [];
			if (!mrs.length) {
				frappe.msgprint(__('No pending Material Requests found for this warehouse'), __('Info'));
				return;
			}

			// Check which MRs are already added
			var already_added = _get_added_sources(frm, 'Material Request');

			var fields = [{
				fieldtype: 'HTML',
				fieldname: 'mr_list_html',
				options: _build_doc_selection_html(mrs, 'Material Request', already_added)
			}];

			var d = new frappe.ui.Dialog({
				title: __('Select Material Request'),
				fields: fields,
				size: 'large',
				primary_action_label: __('Add Selected'),
				primary_action: function() {
					var selected = [];
					d.$wrapper.find('input.wpl-doc-check:checked').each(function() {
						selected.push($(this).data('name'));
					});

					if (!selected.length) {
						frappe.msgprint(__('Please select at least one Material Request'));
						return;
					}

					d.hide();
					_add_documents_to_pick_list(frm, 'Material Request', selected);
				}
			});

			d.show();
		}
	});
}

// ─── Show Stock Transfer Selection Dialog ────────────────────

function _show_st_selection(frm) {
	if (!frm.doc.warehouse) {
		frappe.msgprint(__('Please select a Source Warehouse first'));
		return;
	}

	frappe.call({
		method: 'rmax_custom.rmax_custom.doctype.warehouse_pick_list.warehouse_pick_list.get_pending_stock_transfers',
		args: { warehouse: frm.doc.warehouse },
		freeze: true,
		freeze_message: __('Loading pending Stock Transfers...'),
		callback: function(r) {
			var sts = r.message || [];
			if (!sts.length) {
				frappe.msgprint(__('No pending Stock Transfers found for this warehouse'), __('Info'));
				return;
			}

			var already_added = _get_added_sources(frm, 'Stock Transfer');

			var fields = [{
				fieldtype: 'HTML',
				fieldname: 'st_list_html',
				options: _build_doc_selection_html(sts, 'Stock Transfer', already_added)
			}];

			var d = new frappe.ui.Dialog({
				title: __('Select Stock Transfer'),
				fields: fields,
				size: 'large',
				primary_action_label: __('Add Selected'),
				primary_action: function() {
					var selected = [];
					d.$wrapper.find('input.wpl-doc-check:checked').each(function() {
						selected.push($(this).data('name'));
					});

					if (!selected.length) {
						frappe.msgprint(__('Please select at least one Stock Transfer'));
						return;
					}

					d.hide();
					_add_documents_to_pick_list(frm, 'Stock Transfer', selected);
				}
			});

			d.show();
		}
	});
}

// ─── Build Selection HTML ────────────────────────────────────

function _build_doc_selection_html(docs, doctype, already_added) {
	var html = '<div style="max-height:400px;overflow-y:auto;">';
	html += '<table class="table table-bordered table-hover" style="margin:0;font-size:13px;">';
	html += '<thead><tr>';
	html += '<th style="width:30px;"><input type="checkbox" class="wpl-select-all"></th>';
	html += '<th>' + __('Document') + '</th>';
	html += '<th>' + __('Date') + '</th>';

	if (doctype === 'Material Request') {
		html += '<th>' + __('Target Warehouse') + '</th>';
	} else {
		html += '<th>' + __('Target Warehouse') + '</th>';
	}

	html += '<th>' + __('Items') + '</th>';
	html += '<th>' + __('Status') + '</th>';
	html += '</tr></thead><tbody>';

	docs.forEach(function(doc) {
		var is_added = already_added.indexOf(doc.name) !== -1;
		var disabled = is_added ? ' disabled' : '';
		var row_style = is_added ? ' style="opacity:0.5;background:#f5f5f5;"' : '';
		var urgent_badge = '';

		if (doctype === 'Material Request' && doc.has_urgent) {
			urgent_badge = ' <span style="background:#ef4444;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;">URGENT</span>';
		}

		var target_wh = '';
		if (doctype === 'Material Request') {
			target_wh = doc.set_warehouse || '-';
		} else {
			target_wh = doc.set_target_warehouse || '-';
		}

		var status = '';
		if (doctype === 'Material Request') {
			status = doc.status || '';
		} else {
			status = doc.workflow_state || '';
		}

		var summary = doc.item_summary || '';
		var count_label = doc.item_count > 3 ? ' +' + (doc.item_count - 3) + ' more' : '';

		html += '<tr' + row_style + '>';
		html += '<td><input type="checkbox" class="wpl-doc-check" data-name="' + doc.name + '"' + disabled + '></td>';
		html += '<td><b>' + doc.name + '</b>' + urgent_badge + (is_added ? ' <small class="text-muted">(already added)</small>' : '') + '</td>';
		html += '<td>' + (doc.transaction_date || '') + '</td>';
		html += '<td>' + target_wh + '</td>';
		html += '<td>' + summary + count_label + '</td>';
		html += '<td>' + status + '</td>';
		html += '</tr>';
	});

	html += '</tbody></table></div>';

	// Select all handler
	html += '<script>';
	html += 'cur_dialog.$wrapper.on("change", ".wpl-select-all", function() {';
	html += '  var checked = $(this).prop("checked");';
	html += '  cur_dialog.$wrapper.find(".wpl-doc-check:not(:disabled)").prop("checked", checked);';
	html += '});';
	html += '</script>';

	return html;
}

// ─── Get Already Added Source Names ──────────────────────────

function _get_added_sources(frm, doctype) {
	var names = [];
	(frm.doc.sources || []).forEach(function(src) {
		if (src.source_doctype === doctype && names.indexOf(src.source_name) === -1) {
			names.push(src.source_name);
		}
	});
	return names;
}

// ─── Add Documents to Pick List (with consolidation) ─────────

function _add_documents_to_pick_list(frm, doctype, doc_names) {
	var pending = doc_names.length;
	var total_added = 0;

	doc_names.forEach(function(doc_name) {
		frappe.call({
			method: 'rmax_custom.rmax_custom.doctype.warehouse_pick_list.warehouse_pick_list.get_items_from_document',
			args: {
				source_doctype: doctype,
				source_name: doc_name,
				warehouse: frm.doc.warehouse
			},
			callback: function(r) {
				if (r.message) {
					var data = r.message;

					// Add sources
					(data.sources || []).forEach(function(src) {
						var row = frm.add_child('sources');
						row.source_doctype = src.source_doctype;
						row.source_name = src.source_name;
						row.item_code = src.item_code;
						row.item_name = src.item_name;
						row.qty = src.qty;
						row.is_urgent = src.is_urgent;
					});

					// Merge items — consolidate same item_code
					(data.items || []).forEach(function(item) {
						var existing = _find_existing_item(frm, item.item_code);
						if (existing) {
							// Merge: add qty, update available, keep urgent if any
							existing.qty_to_pick = flt(existing.qty_to_pick) + flt(item.qty_to_pick);
							existing.available_qty = flt(item.available_qty);
							if (item.is_urgent) existing.is_urgent = 1;
							// Append source ref
							if (existing.source_documents) {
								existing.source_documents += ', ' + item.source_documents;
							} else {
								existing.source_documents = item.source_documents;
							}
						} else {
							// New item
							var row = frm.add_child('items');
							row.item_code = item.item_code;
							row.item_name = item.item_name;
							row.qty_to_pick = item.qty_to_pick;
							row.available_qty = item.available_qty;
							row.uom = item.uom;
							row.is_urgent = item.is_urgent;
							row.source_documents = item.source_documents;
						}
						total_added++;
					});
				}

				pending--;
				if (pending === 0) {
					frm.refresh_fields();
					frm.dirty();

					setTimeout(function() {
						_highlight_pick_rows(frm);
					}, 300);

					if (total_added > 0) {
						frappe.show_alert({
							message: __('{0} item(s) added from {1} document(s)', [total_added, doc_names.length]),
							indicator: 'green'
						});
					}
				}
			}
		});
	});
}

// ─── Find Existing Item in Items Table ───────────────────────

function _find_existing_item(frm, item_code) {
	var items = frm.doc.items || [];
	for (var i = 0; i < items.length; i++) {
		if (items[i].item_code === item_code) {
			return items[i];
		}
	}
	return null;
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
