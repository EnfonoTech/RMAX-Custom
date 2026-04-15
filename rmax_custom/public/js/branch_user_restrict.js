/**
 * RMAX: Branch User / Stock User Access Restriction
 *
 * Restricted users (Branch User, Stock User) can ONLY access:
 * - rmax-dashboard (home page)
 * - Sales Invoice, Quotation, Customer, Payment Entry
 * - Purchase Receipt, Purchase Invoice
 * - Material Request, Stock Transfer, Damage Transfer
 * - Item, Item Price, Item Group
 * - Stock Entry
 * - Reports: Stock Sales Report, Collection Report, Stock Balance, Stock Ledger, General Ledger
 * - Their own User profile
 *
 * Everything else is blocked and redirected to dashboard.
 */
(function () {
	"use strict";

	var ALLOWED_DOCTYPES = [
		"Sales Invoice",
		"Quotation",
		"Customer",
		"Payment Entry",
		"Purchase Receipt",
		"Purchase Invoice",
		"Material Request",
		"Stock Transfer",
		"Damage Slip",
		"Damage Transfer",
		"Supplier Code",
		"Item",
		"Item Price",
		"Item Group",
		"Stock Entry",
		"Warehouse Pick List",
		"Address",
		"Contact",
		"File",
		"Comment",
		"Communication",
		"Activity Log",
		"Branch Configuration",
	];

	var ALLOWED_REPORTS = [
		"Stock Sales Report",
		"Collection Report",
		"Stock Balance",
		"Stock Ledger",
		"General Ledger",
	];

	var ALLOWED_PAGES = [
		"rmax-dashboard",
		"user-guide",
		"print",
		"printview",
	];

	/**
	 * Returns true if user is a restricted user (Branch User or Stock User)
	 * but NOT an admin/manager who should have full access.
	 */
	function is_restricted_user() {
		var roles = _get_roles();
		if (!roles) return false;
		// Admins/managers bypass all restrictions
		if (roles.indexOf("System Manager") !== -1) return false;
		if (roles.indexOf("Administrator") !== -1) return false;
		if (roles.indexOf("Stock Manager") !== -1) return false;
		// Branch User, Stock User, or Damage User = restricted
		if (roles.indexOf("Branch User") !== -1) return true;
		if (roles.indexOf("Stock User") !== -1) return true;
		if (roles.indexOf("Damage User") !== -1) return true;
		return false;
	}

	function _get_roles() {
		if (frappe.boot && frappe.boot.user && frappe.boot.user.roles) {
			return frappe.boot.user.roles;
		}
		if (frappe.user_roles && frappe.user_roles.length) {
			return frappe.user_roles;
		}
		return null;
	}

	function is_route_allowed(route) {
		if (!route || !route.length) return false;

		var first = (route[0] || "").toLowerCase();
		var second = route[1] || "";

		if (first === "rmax-dashboard") return true;

		for (var i = 0; i < ALLOWED_PAGES.length; i++) {
			if (first === ALLOWED_PAGES[i].toLowerCase()) return true;
		}

		if (first === "form" || first === "list") {
			for (var j = 0; j < ALLOWED_DOCTYPES.length; j++) {
				if (second === ALLOWED_DOCTYPES[j]) return true;
			}
			return false;
		}

		if (first === "query-report") {
			for (var k = 0; k < ALLOWED_REPORTS.length; k++) {
				if (second === ALLOWED_REPORTS[k]) return true;
			}
			return false;
		}

		if (first === "app") {
			for (var n = 0; n < ALLOWED_PAGES.length; n++) {
				if (second === ALLOWED_PAGES[n]) return true;
			}
			var slug = (second || "").replace(/-/g, " ");
			for (var m = 0; m < ALLOWED_DOCTYPES.length; m++) {
				if (slug.toLowerCase() === ALLOWED_DOCTYPES[m].toLowerCase()) return true;
			}
			if (second === "query-report" && route[2]) {
				for (var p = 0; p < ALLOWED_REPORTS.length; p++) {
					if (route[2] === ALLOWED_REPORTS[p]) return true;
				}
			}
			return false;
		}

		return false;
	}

	function enforce_route() {
		if (!is_restricted_user()) return;
		var route = frappe.get_route();

		// Redirect home-like routes to dashboard
		var first = (route[0] || "").toLowerCase();
		if (!route.length || first === "" || first === "workspaces" ||
			first === "home" || first === "workspace" ||
			first === "welcome-workspace" ||
			(first === "workspace" && (route[1] || "").toLowerCase() === "home") ||
			(first === "workspace" && (route[1] || "").toLowerCase() === "branch user") ||
			(first === "workspace" && (route[1] || "").toLowerCase() === "welcome workspace")) {
			frappe.set_route("rmax-dashboard");
			return;
		}

		if (!is_route_allowed(route)) {
			frappe.set_route("rmax-dashboard");
		}
	}

	function hide_sidebar() {
		if (!is_restricted_user()) return;

		var $sidebar = $(".desk-sidebar");
		if (!$sidebar.length) return;

		$sidebar.find(".standard-sidebar-section").each(function () {
			var $section = $(this);
			$section.find(".desk-sidebar-item, .sidebar-item-container, a.desk-sidebar-item").each(function () {
				var $item = $(this);
				var text = $item.text().trim().toLowerCase();
				var href = ($item.attr("href") || $item.find("a").attr("href") || "").toLowerCase();

				var keep = (text === "home") || (href.indexOf("rmax-dashboard") !== -1);
				if (!keep) $item.hide();
			});
		});

		$sidebar.find(".standard-sidebar-section").each(function () {
			var $section = $(this);
			if ($section.find(".desk-sidebar-item:visible, .sidebar-item-container:visible").length === 0) {
				$section.hide();
			}
		});
	}

	// === FIX LOGO HREF ===
	function fix_logo_href() {
		if (!is_restricted_user()) return;

		$(".navbar-brand, .navbar-home").each(function () {
			var $el = $(this);
			if ($el.attr("href") !== "/app/rmax-dashboard") {
				$el.attr("href", "/app/rmax-dashboard");
			}
			if (!$el.data("rmax-bound")) {
				$el.data("rmax-bound", true);
				$el.on("click", function (e) {
					if (!is_restricted_user()) return;
					e.preventDefault();
					e.stopPropagation();
					frappe.set_route("rmax-dashboard");
					return false;
				});
			}
		});
	}

	// === ADD DASHBOARD BUTTON ===
	function add_dashboard_nav() {
		if (!is_restricted_user()) return;
		if ($("#rmax-dash-nav-btn").length) return;

		var $btn = $('<a id="rmax-dash-nav-btn" href="/app/rmax-dashboard" style="' +
			'display:inline-flex;align-items:center;gap:5px;' +
			'margin-left:12px;padding:4px 14px;' +
			'font-size:12px;font-weight:600;color:#e94560;' +
			'border:1px solid #e94560;border-radius:6px;' +
			'text-decoration:none;vertical-align:middle;' +
			'transition:all 0.15s ease;' +
			'">← Dashboard</a>');

		$btn.on("click", function (e) {
			e.preventDefault();
			e.stopPropagation();
			frappe.set_route("rmax-dashboard");
			return false;
		});
		$btn.on("mouseenter", function () {
			$(this).css({ "background": "#e94560", "color": "#fff" });
		});
		$btn.on("mouseleave", function () {
			$(this).css({ "background": "transparent", "color": "#e94560" });
		});

		var $brand = $(".navbar-brand").first();
		if ($brand.length) {
			$brand.after($btn);
		}
	}

	// === HIDE COST/VALUE COLUMNS IN REPORTS ===
	// Fieldnames that should be hidden in Stock Balance / Stock Ledger
	var COST_FIELDNAMES_TO_HIDE = [
		"opening_value", "val_rate", "in_val", "out_val", "bal_val",
		"valuation_rate", "stock_value", "stock_value_difference",
		"opening_qty_value", "incoming_rate", "outgoing_rate",
		"stock_value_difference"
	];

	// Reports where cost columns should be hidden
	var REPORTS_TO_FILTER = [
		"Stock Balance",
		"Stock Ledger",
	];

	function hide_cost_columns_in_reports() {
		if (!is_restricted_user()) return;
		var route = frappe.get_route();
		if (!route || route[0] !== "query-report") return;

		var report_name = route[1] || "";
		var should_filter = false;
		for (var r = 0; r < REPORTS_TO_FILTER.length; r++) {
			if (report_name === REPORTS_TO_FILTER[r]) { should_filter = true; break; }
		}
		if (!should_filter) return;

		// Wait for report to render, then hide columns
		var attempts = 0;
		var interval = setInterval(function () {
			attempts++;
			if (attempts > 30) { clearInterval(interval); return; }

			var report = frappe.query_report;
			if (!report || !report.columns || !report.columns.length) return;

			clearInterval(interval);

			// Hide cost-related columns
			var changed = false;
			report.columns.forEach(function (col) {
				var id = (col.fieldname || col.id || "").toLowerCase();
				var label = (col.label || col.name || "").toLowerCase();
				var is_cost = false;

				for (var i = 0; i < COST_FIELDNAMES_TO_HIDE.length; i++) {
					if (id === COST_FIELDNAMES_TO_HIDE[i]) { is_cost = true; break; }
				}
				// Also match by label keywords
				if (!is_cost && (
					label.indexOf("value") !== -1 ||
					label.indexOf("valuation") !== -1
				)) {
					// Only hide value/valuation columns, not qty-related
					if (label.indexOf("qty") === -1 && label.indexOf("quantity") === -1) {
						is_cost = true;
					}
				}
				// Hide any "rate" column (incoming rate, outgoing rate, valuation rate)
				if (!is_cost && label.indexOf("rate") !== -1) {
					is_cost = true;
				}

				if (is_cost && !col.hidden) {
					col.hidden = 1;
					changed = true;
				}
			});

			if (changed) {
				report.render_datatable();
			}
		}, 300);
	}

	// === FIX COMPANY DEFAULT FOR RESTRICTED USERS ===
	function fix_company_default() {
		if (!is_restricted_user()) return;
		// If global default is a company user doesn't have access to,
		// override with user's permitted company from boot defaults
		var user_company = (frappe.boot.user_default_company
			|| (frappe.defaults && frappe.defaults.get_user_default("Company"))
			|| "");
		if (user_company) {
			frappe.sys_defaults.company = user_company;
		}
	}

	// === APPLY ALL RESTRICTIONS ===
	function apply_all() {
		if (!is_restricted_user()) return;
		enforce_route();
		hide_sidebar();
		fix_logo_href();
		add_dashboard_nav();
		hide_cost_columns_in_reports();
	}

	// === ENFORCE ON EVERY PAGE CHANGE ===
	$(document).on("page-change", function () {
		setTimeout(apply_all, 200);
	});

	// === ENFORCE ON INITIAL LOAD ===
	$(document).ready(function () {
		var check_count = 0;
		var check_interval = setInterval(function () {
			check_count++;
			if (check_count > 50) {
				clearInterval(check_interval);
				return;
			}
			if (frappe.boot && frappe.boot.user && frappe.boot.user.roles) {
				clearInterval(check_interval);
				if (is_restricted_user()) {
					fix_company_default();
					apply_all();

					// Redirect if on home/workspace
					var r = frappe.get_route();
					if (!r.length || r[0] === "" || r[0] === "Workspaces" ||
						r[0] === "workspaces" || r[0] === "Home" ||
						r[0] === "welcome-workspace" ||
						(r[0] === "Workspace" && r[1] === "Home") ||
						(r[0] === "Workspace" && r[1] === "Welcome Workspace")) {
						frappe.set_route("rmax-dashboard");
					}
				}
			}
		}, 100);
	});

	// Keep polling to fix the logo and add button
	// Navbar is rendered async by Frappe, so we need to keep checking
	setInterval(function () {
		if (is_restricted_user()) {
			fix_logo_href();
			add_dashboard_nav();
		}
	}, 1000);

})();
