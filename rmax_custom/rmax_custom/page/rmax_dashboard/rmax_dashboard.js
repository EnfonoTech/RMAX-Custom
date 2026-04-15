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

	page.main.html('<div class="rmax-dash"><div class="rmax-dash-loading"><div class="loading-spinner"></div><span>Loading dashboard...</span></div></div>');

	frappe.call({
		method: 'rmax_custom.api.dashboard.get_dashboard_data',
		callback: function(r) {
			if (r.message) {
				render_dashboard(page, r.message);
			}
		},
		error: function() {
			page.main.html('<div class="rmax-dash"><p class="dash-error">Failed to load dashboard data.</p></div>');
		}
	});
};

function render_dashboard(page, data) {
	var html = '<div class="rmax-dash">';

	// Header — branch name prominent, company subtle
	html += '<div class="dash-header">';
	html += '<div class="dash-header-left">';
	if (data.is_branch_user && !data.is_admin) {
		var branch = data.branch_name || 'Branch';
		html += '<h2 class="dash-title">' + frappe.utils.escape_html(branch) + ' <span class="dash-title-suffix">Branch</span></h2>';
		html += '<span class="dash-subtitle">Sales Dashboard</span>';
	} else if (data.is_stock_user && !data.is_branch_user && !data.is_admin) {
		html += '<h2 class="dash-title">Warehouse</h2>';
		html += '<span class="dash-subtitle">Stock Operations</span>';
	} else {
		html += '<h2 class="dash-title">Management</h2>';
		html += '<span class="dash-subtitle">Overview Dashboard</span>';
	}
	html += '</div>';
	html += '<div class="dash-header-right">';
	html += '<span class="dash-date">' + frappe.datetime.str_to_user(frappe.datetime.get_today()) + '</span>';
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
		html += '<div class="dash-divider"></div>';
		html += '<h3 class="section-title">Stock Operations</h3>';
		html += render_stock_dashboard(data);
	}

	html += '</div>';
	page.main.html(html);

	// Animate cards in
	setTimeout(function() {
		page.main.find('.kpi-card, .action-card, .pending-item').each(function(i) {
			var $el = $(this);
			setTimeout(function() {
				$el.addClass('card-visible');
			}, i * 40);
		});
	}, 50);

	// Bind click events
	page.main.find('.action-card').on('click', function() {
		var action = $(this).data('action');
		var target = $(this).data('target');
		var filter = $(this).data('filter');
		if (action === 'new') {
			frappe.new_doc(target);
		} else if (action === 'list') {
			if (filter) {
				frappe.set_route('List', target, filter);
			} else {
				frappe.set_route('List', target);
			}
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

	// KPI Cards — prominent, bold, readable
	html += '<div class="kpi-row">';
	html += kpi_card(format_currency_short(data.daily_sales, currency), 'Daily Sales', 'today', '📊');
	html += kpi_card(format_currency_short(data.monthly_sales, currency), 'Monthly Sales', 'month', '📈');
	html += kpi_card(format_number_short(data.mtd_invoices), 'MTD Invoices', 'invoices', '🧾');
	html += kpi_card(format_number_short(data.pending_approvals), 'Pending Approvals', 'pending', '⏳');
	html += kpi_card(format_currency_short(data.credits_outstanding, currency), 'Outstanding', 'outstanding', '💰');
	html += '</div>';

	// Quick Actions — includes returns inline
	html += '<h3 class="section-title">Quick Actions</h3>';
	html += '<div class="action-grid">';
	html += action_card('receipt', 'Sales Invoice', 'Create new invoice', 'new', 'Sales Invoice');
	html += action_card('document', 'Quotation', 'View quotations', 'list', 'Quotation');
	html += action_card('people', 'Customer', 'Manage customers', 'list', 'Customer');
	html += action_card('credit-card', 'Payment Entry', 'Record payments', 'list', 'Payment Entry');
	html += action_card('package', 'Purchase Receipt', 'View receipts', 'list', 'Purchase Receipt');
	html += action_card('file-text', 'Purchase Invoice', 'View invoices', 'list', 'Purchase Invoice');
	html += action_card('truck', 'Material Request', 'Request materials', 'list', 'Material Request');
	html += action_card('shuffle', 'Stock Transfer', 'Transfer stock', 'list', 'Stock Transfer');
	html += action_card('corner-down-left', 'Sales Return', 'Process returns', 'list', 'Sales Invoice', 'is_return=1');
	html += action_card('corner-down-right', 'Purchase Return', 'Process returns', 'list', 'Purchase Invoice', 'is_return=1');
	html += '</div>';

	// Reports
	html += '<h3 class="section-title">Reports</h3>';
	html += '<div class="action-grid">';
	html += action_card('bar-chart-2', 'Stock Sales Report', 'Sales analysis', 'report', 'Stock Sales Report');
	html += action_card('dollar-sign', 'Collection Report', 'Payment collections', 'report', 'Collection Report');
	html += action_card('layers', 'Stock Balance', 'Current stock levels', 'report', 'Stock Balance');
	html += action_card('book-open', 'Stock Ledger', 'Stock transactions', 'report', 'Stock Ledger');
	html += action_card('user', 'Customer Statement', 'Account statements', 'report', 'General Ledger');
	html += action_card('list', 'Item List', 'Browse items', 'list', 'Item');
	html += action_card('tag', 'Price List', 'View price lists', 'list', 'Item Price');
	html += '</div>';

	// Pending Approvals
	if (data.pending_transfers && data.pending_transfers.length > 0) {
		html += '<h3 class="section-title">Pending Approvals</h3>';
		html += '<div class="pending-list">';
		data.pending_transfers.forEach(function(st) {
			html += '<div class="pending-item">';
			html += '<div class="pending-info">';
			html += '<a class="pending-link" data-name="' + frappe.utils.escape_html(st.name) + '">';
			html += frappe.utils.escape_html(st.name) + '</a>';
			html += '<div class="pending-route">';
			html += '<span class="wh-from">' + frappe.utils.escape_html(st.set_source_warehouse || '') + '</span>';
			html += '<span class="route-arrow">→</span>';
			html += '<span class="wh-to">' + frappe.utils.escape_html(st.set_target_warehouse || '') + '</span>';
			html += '</div>';
			html += '</div>';
			html += '<div class="pending-meta">';
			html += '<div class="pending-date">' + frappe.datetime.str_to_user(st.transaction_date) + '</div>';
			html += '<div class="pending-status">Waiting</div>';
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
	html += kpi_card(format_number_short(data.pending_mrs || 0), 'Pending MRs', 'pending', '📋');
	html += kpi_card(format_number_short(data.pending_sts || 0), 'Pending STs', 'outstanding', '📦');
	html += kpi_card(format_number_short(data.total_items || 0), 'Total Items', 'invoices', '🏷️');
	html += kpi_card('--', 'Low Stock Items', 'month', '⚠️');
	html += '</div>';

	// Quick Actions
	html += '<h3 class="section-title">Stock Actions</h3>';
	html += '<div class="action-grid">';
	html += action_card('shuffle', 'Stock Transfer', 'Create new transfer', 'new', 'Stock Transfer');
	html += action_card('truck', 'Material Request', 'View requests', 'list', 'Material Request');
	html += action_card('package', 'Purchase Receipt', 'Receive goods', 'list', 'Purchase Receipt');
	html += action_card('list', 'Item', 'Manage items', 'list', 'Item');
	html += action_card('layers', 'Stock Balance', 'Current stock levels', 'report', 'Stock Balance');
	html += action_card('book-open', 'Stock Ledger', 'Stock transactions', 'report', 'Stock Ledger');
	html += action_card('tag', 'Item Groups', 'Browse item groups', 'list', 'Item Group');
	html += action_card('activity', 'Stock Movement', 'Movement report', 'report', 'Stock Ledger');
	html += '</div>';

	return html;
}

function kpi_card(value, label, type, emoji) {
	return '<div class="kpi-card kpi-' + type + '">'
		+ '<div class="kpi-top">'
		+ '<span class="kpi-emoji">' + emoji + '</span>'
		+ '<span class="kpi-label">' + frappe.utils.escape_html(label) + '</span>'
		+ '</div>'
		+ '<div class="kpi-value">' + value + '</div>'
		+ '</div>';
}

// SVG icon paths for action cards (Feather icons subset)
var ICONS = {
	'receipt': '<path d="M14 2H6a2 2 0 0 0-2 2v16l4-2 4 2 4-2 4 2V4a2 2 0 0 0-2-2z"/>',
	'document': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>',
	'people': '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
	'credit-card': '<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>',
	'package': '<line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
	'file-text': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
	'truck': '<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
	'shuffle': '<polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/>',
	'corner-down-left': '<polyline points="9 10 4 15 9 20"/><path d="M20 4v7a4 4 0 0 1-4 4H4"/>',
	'corner-down-right': '<polyline points="15 10 20 15 15 20"/><path d="M4 4v7a4 4 0 0 0 4 4h12"/>',
	'bar-chart-2': '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
	'dollar-sign': '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
	'layers': '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
	'book-open': '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
	'user': '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
	'list': '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
	'tag': '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>',
	'activity': '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
};

function get_icon_svg(name) {
	var path = ICONS[name] || '';
	return '<svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' + path + '</svg>';
}

function action_card(icon, title, desc, action, target, extra_filter) {
	var data_attrs = 'data-action="' + action + '" data-target="' + frappe.utils.escape_html(target) + '"';
	if (extra_filter) {
		data_attrs += ' data-filter="' + frappe.utils.escape_html(extra_filter) + '"';
	}
	return '<div class="action-card" ' + data_attrs + '>'
		+ '<div class="card-icon-wrap">' + get_icon_svg(icon) + '</div>'
		+ '<div class="card-text">'
		+ '<div class="card-title">' + frappe.utils.escape_html(title) + '</div>'
		+ '<div class="card-desc">' + frappe.utils.escape_html(desc) + '</div>'
		+ '</div>'
		+ '</div>';
}

function format_currency_short(value, currency) {
	if (!value && value !== 0) return '0';
	var num = parseFloat(value);
	if (isNaN(num)) return '0';
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
		/* ─── Base ─────────────────────────────────── */
		.rmax-dash {
			padding: 24px 28px;
			max-width: 1260px;
			margin: 0 auto;
		}
		.rmax-dash .rmax-dash-loading {
			display: flex;
			align-items: center;
			justify-content: center;
			gap: 12px;
			padding: 80px 20px;
			color: #8492a6;
			font-size: 14px;
		}
		.rmax-dash .loading-spinner {
			width: 20px;
			height: 20px;
			border: 2px solid #e0e6ed;
			border-top-color: #e94560;
			border-radius: 50%;
			animation: rmax-spin 0.6s linear infinite;
		}
		@keyframes rmax-spin {
			to { transform: rotate(360deg); }
		}
		.rmax-dash .dash-error {
			text-align: center;
			padding: 60px 20px;
			color: #e94560;
			font-size: 14px;
		}

		/* ─── Header ───────────────────────────────── */
		.rmax-dash .dash-header {
			display: flex;
			justify-content: space-between;
			align-items: flex-end;
			margin-bottom: 28px;
			padding-bottom: 20px;
			border-bottom: 1px solid #e8ecf1;
		}
		.rmax-dash .dash-title {
			font-size: 26px;
			font-weight: 800;
			color: #1a1a2e;
			margin: 0;
			letter-spacing: -0.5px;
			line-height: 1.2;
		}
		.rmax-dash .dash-title-suffix {
			font-weight: 400;
			color: #8492a6;
		}
		.rmax-dash .dash-subtitle {
			font-size: 13px;
			color: #8492a6;
			margin-top: 4px;
			display: block;
			letter-spacing: 0.3px;
		}
		.rmax-dash .dash-date {
			font-size: 13px;
			color: #8492a6;
			background: #f4f6f9;
			padding: 6px 14px;
			border-radius: 20px;
			font-weight: 500;
		}
		.rmax-dash .dash-divider {
			height: 1px;
			background: #e8ecf1;
			margin: 36px 0 12px;
			border: none;
		}

		/* ─── KPI Cards ────────────────────────────── */
		.rmax-dash .kpi-row {
			display: grid;
			grid-template-columns: repeat(5, 1fr);
			gap: 14px;
			margin-bottom: 32px;
		}
		.rmax-dash .kpi-card {
			background: #fff;
			border-radius: 14px;
			padding: 20px 18px;
			border: 1px solid #e8ecf1;
			position: relative;
			overflow: hidden;
			opacity: 0;
			transform: translateY(12px);
			transition: opacity 0.35s ease, transform 0.35s ease, box-shadow 0.2s ease;
		}
		.rmax-dash .kpi-card.card-visible {
			opacity: 1;
			transform: translateY(0);
		}
		.rmax-dash .kpi-card:hover {
			box-shadow: 0 4px 16px rgba(0,0,0,0.06);
		}
		.rmax-dash .kpi-card::before {
			content: '';
			position: absolute;
			top: 0;
			left: 0;
			right: 0;
			height: 3px;
		}
		.rmax-dash .kpi-today::before { background: #10b981; }
		.rmax-dash .kpi-month::before { background: #3b82f6; }
		.rmax-dash .kpi-invoices::before { background: #6366f1; }
		.rmax-dash .kpi-pending::before { background: #f59e0b; }
		.rmax-dash .kpi-outstanding::before { background: #ef4444; }
		.rmax-dash .kpi-top {
			display: flex;
			align-items: center;
			gap: 6px;
			margin-bottom: 10px;
		}
		.rmax-dash .kpi-emoji {
			font-size: 16px;
			line-height: 1;
		}
		.rmax-dash .kpi-label {
			font-size: 11px;
			font-weight: 600;
			text-transform: uppercase;
			letter-spacing: 0.8px;
			color: #8492a6;
		}
		.rmax-dash .kpi-value {
			font-size: 32px;
			font-weight: 800;
			line-height: 1;
			color: #1a1a2e;
			letter-spacing: -1px;
		}

		/* KPI color accents on values */
		.rmax-dash .kpi-today .kpi-value { color: #059669; }
		.rmax-dash .kpi-month .kpi-value { color: #2563eb; }
		.rmax-dash .kpi-invoices .kpi-value { color: #4f46e5; }
		.rmax-dash .kpi-pending .kpi-value { color: #d97706; }
		.rmax-dash .kpi-outstanding .kpi-value { color: #dc2626; }

		/* ─── Section Title ────────────────────────── */
		.rmax-dash .section-title {
			font-size: 15px;
			font-weight: 700;
			margin: 28px 0 14px;
			color: #1a1a2e;
			text-transform: uppercase;
			letter-spacing: 0.5px;
		}

		/* ─── Action Cards ─────────────────────────── */
		.rmax-dash .action-grid {
			display: grid;
			grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
			gap: 10px;
		}
		.rmax-dash .action-card {
			display: flex;
			align-items: center;
			gap: 14px;
			background: #fff;
			border-radius: 12px;
			padding: 16px 18px;
			border: 1px solid #e8ecf1;
			cursor: pointer;
			transition: all 0.2s ease;
			opacity: 0;
			transform: translateY(8px);
		}
		.rmax-dash .action-card.card-visible {
			opacity: 1;
			transform: translateY(0);
		}
		.rmax-dash .action-card:hover {
			border-color: #e94560;
			box-shadow: 0 4px 14px rgba(233, 69, 96, 0.08);
			transform: translateY(-2px);
		}
		.rmax-dash .action-card:active {
			transform: translateY(0);
		}
		.rmax-dash .card-icon-wrap {
			flex-shrink: 0;
			width: 38px;
			height: 38px;
			display: flex;
			align-items: center;
			justify-content: center;
			border-radius: 10px;
			background: #f4f6f9;
			color: #5a6c7d;
			transition: all 0.2s;
		}
		.rmax-dash .action-card:hover .card-icon-wrap {
			background: #fef2f2;
			color: #e94560;
		}
		.rmax-dash .action-icon {
			width: 18px;
			height: 18px;
		}
		.rmax-dash .card-title {
			font-size: 13px;
			font-weight: 600;
			color: #1a1a2e;
			line-height: 1.3;
		}
		.rmax-dash .card-desc {
			font-size: 11px;
			color: #8492a6;
			margin-top: 2px;
		}

		/* ─── Pending Approvals ────────────────────── */
		.rmax-dash .pending-list {
			background: #fff;
			border-radius: 14px;
			padding: 8px 0;
			border: 1px solid #e8ecf1;
		}
		.rmax-dash .pending-item {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 14px 20px;
			border-bottom: 1px solid #f0f3f7;
			opacity: 0;
			transform: translateX(-8px);
			transition: opacity 0.3s ease, transform 0.3s ease, background 0.15s ease;
		}
		.rmax-dash .pending-item.card-visible {
			opacity: 1;
			transform: translateX(0);
		}
		.rmax-dash .pending-item:last-child {
			border-bottom: 0;
		}
		.rmax-dash .pending-item:hover {
			background: #fafbfd;
		}
		.rmax-dash .pending-link {
			cursor: pointer;
			color: #2563eb;
			font-weight: 700;
			font-size: 13px;
			text-decoration: none;
		}
		.rmax-dash .pending-link:hover {
			color: #e94560;
			text-decoration: underline;
		}
		.rmax-dash .pending-route {
			font-size: 12px;
			color: #8492a6;
			margin-top: 4px;
			display: flex;
			align-items: center;
			gap: 6px;
		}
		.rmax-dash .route-arrow {
			color: #c0c9d4;
			font-weight: 700;
		}
		.rmax-dash .pending-meta {
			text-align: right;
			flex-shrink: 0;
		}
		.rmax-dash .pending-date {
			font-size: 12px;
			color: #8492a6;
		}
		.rmax-dash .pending-status {
			font-size: 11px;
			color: #d97706;
			font-weight: 600;
			margin-top: 3px;
			text-transform: uppercase;
			letter-spacing: 0.5px;
		}

		/* ─── Responsive ───────────────────────────── */
		@media (max-width: 1100px) {
			.rmax-dash .kpi-row {
				grid-template-columns: repeat(3, 1fr);
			}
		}
		@media (max-width: 768px) {
			.rmax-dash {
				padding: 16px;
			}
			.rmax-dash .kpi-row {
				grid-template-columns: repeat(2, 1fr);
				gap: 10px;
			}
			.rmax-dash .kpi-value {
				font-size: 26px;
			}
			.rmax-dash .action-grid {
				grid-template-columns: repeat(2, 1fr);
				gap: 8px;
			}
			.rmax-dash .action-card {
				padding: 14px;
				gap: 10px;
			}
			.rmax-dash .card-icon-wrap {
				width: 34px;
				height: 34px;
			}
			.rmax-dash .dash-header {
				flex-direction: column;
				align-items: flex-start;
				gap: 10px;
			}
		}
		@media (max-width: 480px) {
			.rmax-dash .kpi-row {
				grid-template-columns: 1fr 1fr;
			}
			.rmax-dash .kpi-card {
				padding: 16px 14px;
			}
			.rmax-dash .kpi-value {
				font-size: 22px;
			}
			.rmax-dash .action-grid {
				grid-template-columns: 1fr;
			}
			.rmax-dash .pending-item {
				flex-direction: column;
				align-items: flex-start;
				gap: 6px;
			}
			.rmax-dash .pending-meta {
				text-align: left;
			}
		}
	`;
}
