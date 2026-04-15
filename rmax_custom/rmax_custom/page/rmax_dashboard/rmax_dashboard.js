frappe.pages['rmax-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Dashboard',
		single_column: true
	});

	// Inject CSS
	if (!document.getElementById('rmax-dash-style')) {
		var style = document.createElement('style');
		style.id = 'rmax-dash-style';
		style.textContent = get_dashboard_css();
		document.head.appendChild(style);
	}

	page.main.html('<div class="rmax-dash"><div class="rmax-dash-loading">Loading dashboard...</div></div>');

	frappe.call({
		method: 'rmax_custom.api.dashboard.get_dashboard_data',
		callback: function(r) {
			if (r.message) {
				render_dashboard(page, r.message);
			}
		},
		error: function() {
			page.main.html('<div class="rmax-dash"><p style="color:#d63031;">Failed to load dashboard data.</p></div>');
		}
	});
};

function render_dashboard(page, data) {
	var html = '<div class="rmax-dash">';

	// Header
	html += '<div class="dash-header">';
	html += '<div>';
	html += '<h2 class="dash-company">RMAX</h2>';
	if (data.is_branch_user && !data.is_admin) {
		html += '<span class="dash-subtitle">' + (data.branch_name ? frappe.utils.escape_html(data.branch_name) : 'Sales') + '</span>';
	} else if (data.is_stock_user && !data.is_branch_user && !data.is_admin) {
		html += '<span class="dash-subtitle">Warehouse</span>';
	} else {
		html += '<span class="dash-subtitle">Management</span>';
	}
	html += '</div>';
	html += '</div>';

	// Branch User: sales dashboard ONLY — no stock section
	if (data.is_branch_user && !data.is_admin) {
		html += render_branch_dashboard(data);
	}
	// Stock User (not branch user): stock dashboard only
	else if (data.is_stock_user && !data.is_branch_user && !data.is_admin) {
		html += render_stock_dashboard(data);
	}
	// Admin/Stock Manager: sees both
	else if (data.is_admin) {
		html += render_branch_dashboard(data);
		html += '<hr class="dash-divider">';
		html += '<h3 class="section-title" style="margin-top:32px;">Stock Operations</h3>';
		html += render_stock_dashboard(data);
	}

	html += '</div>';
	page.main.html(html);

	// Bind click events
	page.main.find('.action-card').on('click', function() {
		var action = $(this).data('action');
		var target = $(this).data('target');
		if (action === 'new') {
			frappe.new_doc(target);
		} else if (action === 'list') {
			frappe.set_route('List', target);
		} else if (action === 'report') {
			frappe.set_route('query-report', target);
		}
	});

	page.main.find('.pending-link').on('click', function() {
		var name = $(this).data('name');
		frappe.set_route('Form', 'Stock Transfer', name);
	});
}

function render_branch_dashboard(data) {
	var currency = data.currency || 'SAR';
	var html = '';

	// KPI Row
	html += '<div class="kpi-row">';
	html += kpi_card(format_currency_short(data.daily_sales, currency), 'Daily Sales', '#00b894');
	html += kpi_card(format_currency_short(data.monthly_sales, currency), 'Monthly Sales', '#0984e3');
	html += kpi_card(format_number_short(data.mtd_invoices), 'MTD Invoices', '#2d3436');
	html += kpi_card(format_number_short(data.pending_approvals), 'Pending Approvals', '#e17055');
	html += kpi_card(format_currency_short(data.credits_outstanding, currency), 'Credits Outstanding', '#d63031');
	html += '</div>';

	// Quick Actions
	html += '<h3 class="section-title">Quick Actions</h3>';
	html += '<div class="action-grid">';
	html += action_card('\uD83E\uDDFE', 'Sales Invoice', 'Create new sales invoice', 'new', 'Sales Invoice');
	html += action_card('\uD83D\uDCCB', 'Quotation', 'View quotations', 'list', 'Quotation');
	html += action_card('\uD83D\uDC64', 'Customer', 'Manage customers', 'list', 'Customer');
	html += action_card('\uD83D\uDCB3', 'Payment Entry', 'Record payments', 'list', 'Payment Entry');
	html += action_card('\uD83D\uDCE6', 'Purchase Receipt', 'View receipts', 'list', 'Purchase Receipt');
	html += action_card('\uD83D\uDCC4', 'Purchase Invoice', 'View purchase invoices', 'list', 'Purchase Invoice');
	html += action_card('\uD83D\uDE9A', 'Material Request', 'Request materials', 'list', 'Material Request');
	html += action_card('\uD83D\uDCE4', 'Stock Transfer', 'Transfer stock', 'list', 'Stock Transfer');
	html += '</div>';

	// Returns
	html += '<h3 class="section-title">Returns</h3>';
	html += '<div class="action-grid">';
	html += action_card('\u21A9\uFE0F', 'Sales Return', 'Process sales returns', 'list', 'Sales Invoice', 'is_return=1');
	html += action_card('\u21AA\uFE0F', 'Purchase Return', 'Process purchase returns', 'list', 'Purchase Invoice', 'is_return=1');
	html += '</div>';

	// Reports
	html += '<h3 class="section-title">Reports</h3>';
	html += '<div class="action-grid">';
	html += action_card('\uD83D\uDCC8', 'Stock Sales Report', 'Sales analysis', 'report', 'Stock Sales Report');
	html += action_card('\uD83D\uDCB0', 'Collection Report', 'Payment collections', 'report', 'Collection Report');
	html += action_card('\uD83D\uDCCA', 'Stock Balance', 'Current stock levels', 'report', 'Stock Balance');
	html += action_card('\uD83D\uDCD2', 'Stock Ledger', 'Stock transactions', 'report', 'Stock Ledger');
	html += action_card('\uD83D\uDCC3', 'Customer Statement', 'Account statements', 'report', 'General Ledger');
	html += action_card('\uD83D\uDCDD', 'Item List', 'Browse items', 'list', 'Item');
	html += action_card('\uD83D\uDCB2', 'Price List', 'View price lists', 'list', 'Item Price');
	html += '</div>';

	// Pending Approvals
	if (data.pending_transfers && data.pending_transfers.length > 0) {
		html += '<h3 class="section-title">Pending Approvals</h3>';
		html += '<div class="pending-list">';
		data.pending_transfers.forEach(function(st) {
			html += '<div class="pending-item">';
			html += '<div>';
			html += '<a class="pending-link" data-name="' + frappe.utils.escape_html(st.name) + '" style="cursor:pointer;color:#0984e3;font-weight:600;">';
			html += frappe.utils.escape_html(st.name) + '</a>';
			html += '<div style="font-size:12px;color:#6c757d;margin-top:2px;">';
			html += frappe.utils.escape_html(st.set_source_warehouse || '') + ' &rarr; ' + frappe.utils.escape_html(st.set_target_warehouse || '');
			html += '</div>';
			html += '</div>';
			html += '<div style="text-align:right;">';
			html += '<div style="font-size:12px;color:#6c757d;">' + frappe.datetime.str_to_user(st.transaction_date) + '</div>';
			html += '<div style="font-size:11px;color:#e17055;margin-top:2px;">Waiting for Approval</div>';
			html += '</div>';
			html += '</div>';
		});
		html += '</div>';
	}

	return html;
}

function render_stock_dashboard(data) {
	var html = '';

	// KPI Row
	html += '<div class="kpi-row">';
	html += kpi_card(format_number_short(data.pending_mrs || 0), 'Pending MRs', '#e17055');
	html += kpi_card(format_number_short(data.pending_sts || 0), 'Pending STs', '#d63031');
	html += kpi_card(format_number_short(data.total_items || 0), 'Total Items', '#0984e3');
	html += kpi_card('--', 'Low Stock Items', '#2d3436');
	html += '</div>';

	// Quick Actions
	html += '<h3 class="section-title">Stock Actions</h3>';
	html += '<div class="action-grid">';
	html += action_card('\uD83D\uDCE4', 'Stock Transfer', 'Create new transfer', 'new', 'Stock Transfer');
	html += action_card('\uD83D\uDE9A', 'Material Request', 'View requests', 'list', 'Material Request');
	html += action_card('\uD83D\uDCE6', 'Purchase Receipt', 'Receive goods', 'list', 'Purchase Receipt');
	html += action_card('\uD83D\uDCDD', 'Item', 'Manage items', 'list', 'Item');
	html += action_card('\uD83D\uDCCA', 'Stock Balance', 'Current stock levels', 'report', 'Stock Balance');
	html += action_card('\uD83D\uDCD2', 'Stock Ledger', 'Stock transactions', 'report', 'Stock Ledger');
	html += action_card('\uD83C\uDFF7\uFE0F', 'Item Groups', 'Browse item groups', 'list', 'Item Group');
	html += action_card('\uD83D\uDD04', 'Stock Movement', 'Movement report', 'report', 'Stock Ledger');
	html += '</div>';

	return html;
}

function kpi_card(value, label, color) {
	return '<div class="kpi-card">'
		+ '<div class="kpi-value" style="color:' + color + ';">' + value + '</div>'
		+ '<div class="kpi-label">' + frappe.utils.escape_html(label) + '</div>'
		+ '</div>';
}

function action_card(icon, title, desc, action, target, extra_filter) {
	var data_attrs = 'data-action="' + action + '" data-target="' + frappe.utils.escape_html(target) + '"';
	if (extra_filter) {
		data_attrs += ' data-filter="' + frappe.utils.escape_html(extra_filter) + '"';
	}
	return '<div class="action-card" ' + data_attrs + '>'
		+ '<div class="card-icon">' + icon + '</div>'
		+ '<div class="card-title">' + frappe.utils.escape_html(title) + '</div>'
		+ '<div class="card-desc">' + frappe.utils.escape_html(desc) + '</div>'
		+ '</div>';
}

function format_currency_short(value, currency) {
	if (!value && value !== 0) return '--';
	var num = parseFloat(value);
	if (isNaN(num)) return '--';
	if (num >= 1000000) {
		return (num / 1000000).toFixed(1) + 'M';
	} else if (num >= 1000) {
		return (num / 1000).toFixed(num >= 100000 ? 0 : 1) + 'K';
	}
	return num.toLocaleString(undefined, {maximumFractionDigits: 0});
}

function format_number_short(value) {
	if (!value && value !== 0) return '0';
	var num = parseInt(value);
	if (isNaN(num)) return '0';
	if (num >= 1000000) {
		return (num / 1000000).toFixed(1) + 'M';
	} else if (num >= 1000) {
		return (num / 1000).toFixed(1) + 'K';
	}
	return num.toLocaleString();
}

function get_dashboard_css() {
	return `
		.rmax-dash {
			padding: 20px;
			max-width: 1200px;
			margin: 0 auto;
		}
		.rmax-dash .rmax-dash-loading {
			text-align: center;
			padding: 60px 20px;
			color: #6c757d;
			font-size: 14px;
		}
		.rmax-dash .dash-header {
			display: flex;
			justify-content: space-between;
			align-items: flex-start;
			margin-bottom: 24px;
		}
		.rmax-dash .dash-company {
			font-size: 22px;
			font-weight: 700;
			color: #1a1a2e;
			margin: 0;
		}
		.rmax-dash .dash-subtitle {
			font-size: 13px;
			color: #6c757d;
			margin-top: 2px;
			display: block;
		}
		.rmax-dash .dash-settings-btn {
			border-radius: 8px;
			font-size: 12px;
		}
		.rmax-dash .dash-divider {
			border: none;
			border-top: 1px solid #eee;
			margin: 32px 0 8px;
		}
		.rmax-dash .kpi-row {
			display: flex;
			gap: 16px;
			margin-bottom: 24px;
			flex-wrap: wrap;
		}
		.rmax-dash .kpi-card {
			flex: 1;
			min-width: 160px;
			background: white;
			border-radius: 12px;
			padding: 20px;
			box-shadow: 0 1px 3px rgba(0,0,0,0.08);
			text-align: center;
		}
		.rmax-dash .kpi-value {
			font-size: 28px;
			font-weight: 700;
			line-height: 1.2;
		}
		.rmax-dash .kpi-label {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: 1px;
			color: #6c757d;
			margin-top: 6px;
		}
		.rmax-dash .section-title {
			font-size: 16px;
			font-weight: 600;
			margin: 24px 0 12px;
			color: #1a1a2e;
		}
		.rmax-dash .action-grid {
			display: grid;
			grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
			gap: 12px;
		}
		.rmax-dash .action-card {
			background: white;
			border-radius: 10px;
			padding: 20px;
			box-shadow: 0 1px 3px rgba(0,0,0,0.06);
			cursor: pointer;
			transition: all 0.2s;
			border: 1px solid #f0f0f0;
		}
		.rmax-dash .action-card:hover {
			box-shadow: 0 4px 12px rgba(0,0,0,0.1);
			transform: translateY(-2px);
			border-color: #e94560;
		}
		.rmax-dash .action-card .card-icon {
			font-size: 28px;
			margin-bottom: 10px;
		}
		.rmax-dash .action-card .card-title {
			font-size: 14px;
			font-weight: 600;
			color: #1a1a2e;
		}
		.rmax-dash .action-card .card-desc {
			font-size: 12px;
			color: #6c757d;
			margin-top: 4px;
		}
		.rmax-dash .pending-list {
			background: white;
			border-radius: 10px;
			padding: 16px;
			box-shadow: 0 1px 3px rgba(0,0,0,0.06);
		}
		.rmax-dash .pending-item {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 10px 0;
			border-bottom: 1px solid #f0f0f0;
		}
		.rmax-dash .pending-item:last-child {
			border: 0;
		}

		/* Responsive */
		@media (max-width: 768px) {
			.rmax-dash {
				padding: 12px;
			}
			.rmax-dash .kpi-row {
				gap: 10px;
			}
			.rmax-dash .kpi-card {
				min-width: 140px;
				padding: 14px;
			}
			.rmax-dash .kpi-value {
				font-size: 22px;
			}
			.rmax-dash .action-grid {
				grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
				gap: 8px;
			}
			.rmax-dash .action-card {
				padding: 14px;
			}
			.rmax-dash .action-card .card-icon {
				font-size: 22px;
				margin-bottom: 6px;
			}
			.rmax-dash .dash-header {
				flex-direction: column;
				gap: 12px;
			}
		}

		@media (max-width: 480px) {
			.rmax-dash .kpi-card {
				min-width: 100%;
			}
			.rmax-dash .action-grid {
				grid-template-columns: 1fr 1fr;
			}
		}
	`;
}
