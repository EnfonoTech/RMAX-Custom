/**
 * RMAX: Branch User Access Restriction
 *
 * Branch Users can ONLY access:
 * - rmax-dashboard (home page)
 * - Sales Invoice, Quotation, Customer, Payment Entry
 * - Purchase Receipt, Purchase Invoice
 * - Material Request, Stock Transfer, Damage Transfer
 * - Item, Item Price
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
		"Damage Transfer",
		"Item",
		"Item Price",
		"Item Group",
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

	function is_branch_user() {
		// Check boot info (most reliable)
		if (frappe.boot && frappe.boot.user && frappe.boot.user.roles) {
			var roles = frappe.boot.user.roles;
			if (roles.indexOf("System Manager") !== -1) return false;
			if (roles.indexOf("Administrator") !== -1) return false;
			if (roles.indexOf("Stock Manager") !== -1) return false;
			if (roles.indexOf("Branch User") !== -1) return true;
		}
		// Fallback to user_roles
		if (frappe.user_roles && frappe.user_roles.length) {
			if (frappe.user_roles.indexOf("System Manager") !== -1) return false;
			if (frappe.user_roles.indexOf("Administrator") !== -1) return false;
			if (frappe.user_roles.indexOf("Stock Manager") !== -1) return false;
			if (frappe.user_roles.indexOf("Branch User") !== -1) return true;
		}
		return false;
	}

	function is_route_allowed(route) {
		if (!route || !route.length) return false;

		var first = (route[0] || "").toLowerCase();
		var second = route[1] || "";

		// Always allow dashboard
		if (first === "rmax-dashboard") return true;

		// Allow specific pages
		for (var i = 0; i < ALLOWED_PAGES.length; i++) {
			if (first === ALLOWED_PAGES[i].toLowerCase()) return true;
		}

		// Allow Form and List views for allowed DocTypes
		if (first === "form" || first === "list") {
			for (var j = 0; j < ALLOWED_DOCTYPES.length; j++) {
				if (second === ALLOWED_DOCTYPES[j]) return true;
			}
			return false;
		}

		// Allow query-report for allowed reports
		if (first === "query-report") {
			for (var k = 0; k < ALLOWED_REPORTS.length; k++) {
				if (second === ALLOWED_REPORTS[k]) return true;
			}
			return false;
		}

		// Allow app/doctype patterns (URL style used by Frappe v15)
		if (first === "app") {
			// app/rmax-dashboard
			for (var n = 0; n < ALLOWED_PAGES.length; n++) {
				if (second === ALLOWED_PAGES[n]) return true;
			}
			// app/sales-invoice, app/sales-invoice/SI-00001
			var slug = (second || "").replace(/-/g, " ");
			for (var m = 0; m < ALLOWED_DOCTYPES.length; m++) {
				if (slug.toLowerCase() === ALLOWED_DOCTYPES[m].toLowerCase()) return true;
			}
			// app/query-report/Stock Sales Report
			if (second === "query-report" && route[2]) {
				for (var p = 0; p < ALLOWED_REPORTS.length; p++) {
					if (route[2] === ALLOWED_REPORTS[p]) return true;
				}
			}
			return false;
		}

		// Block workspace, module, home, setup pages
		return false;
	}

	function enforce_route() {
		if (!is_branch_user()) return;
		var route = frappe.get_route();
		if (!is_route_allowed(route)) {
			frappe.set_route("rmax-dashboard");
		}
	}

	function hide_sidebar() {
		if (!is_branch_user()) return;

		// Hide ALL sidebar items, then show only allowed ones
		var $sidebar = $(".desk-sidebar");
		if (!$sidebar.length) return;

		// Hide everything in sidebar
		$sidebar.find(".standard-sidebar-section").each(function () {
			var $section = $(this);

			$section.find(".desk-sidebar-item, .sidebar-item-container, a.desk-sidebar-item").each(function () {
				var $item = $(this);
				var text = $item.text().trim();
				var href = ($item.attr("href") || $item.find("a").attr("href") || "").toLowerCase();

				// Only keep specific items
				var keep = false;
				var allowed_sidebar = ["home"];

				for (var i = 0; i < allowed_sidebar.length; i++) {
					if (text.toLowerCase() === allowed_sidebar[i]) {
						keep = true;
						break;
					}
				}

				// Check href for dashboard
				if (href.indexOf("rmax-dashboard") !== -1) keep = true;

				if (!keep) {
					$item.hide();
				}
			});
		});

		// Also hide section headers for hidden sections
		$sidebar.find(".standard-sidebar-section").each(function () {
			var $section = $(this);
			var visible_items = $section.find(".desk-sidebar-item:visible, .sidebar-item-container:visible").length;
			if (visible_items === 0) {
				$section.hide();
			}
		});
	}

	// === INTERCEPT NAVBAR LOGO CLICK ===
	function intercept_logo_click() {
		if (!is_branch_user()) return;
		// Frappe navbar logo — redirect to dashboard instead of Home
		$(document).on("click", ".navbar-brand, .navbar-home, .erpnext-icon, a[href='/app'], a[href='/app/home']", function (e) {
			e.preventDefault();
			e.stopPropagation();
			frappe.set_route("rmax-dashboard");
			return false;
		});

		// Also make the logo element have a pointer cursor
		$(".navbar-brand, .navbar-home").css("cursor", "pointer");
	}

	// === ADD DASHBOARD BUTTON IN NAVBAR ===
	function add_dashboard_nav() {
		if (!is_branch_user()) return;
		if ($("#rmax-dash-nav-btn").length) return;

		// Add a "Dashboard" button next to the logo in the navbar
		var $btn = $('<a id="rmax-dash-nav-btn" href="#" style="' +
			'display:inline-flex;align-items:center;gap:5px;' +
			'margin-left:12px;padding:4px 14px;' +
			'font-size:12px;font-weight:600;color:#e94560;' +
			'border:1px solid #e94560;border-radius:6px;' +
			'text-decoration:none;vertical-align:middle;' +
			'transition:all 0.15s ease;' +
			'">← Dashboard</a>');

		$btn.on("click", function(e) {
			e.preventDefault();
			frappe.set_route("rmax-dashboard");
		});
		$btn.on("mouseenter", function() {
			$(this).css({"background": "#e94560", "color": "#fff"});
		});
		$btn.on("mouseleave", function() {
			$(this).css({"background": "transparent", "color": "#e94560"});
		});

		// Insert after the navbar brand / logo
		var $brand = $(".navbar-brand, .navbar-home").first();
		if ($brand.length) {
			$brand.after($btn);
		} else {
			$(".navbar .container").prepend($btn);
		}
	}

	// === ENFORCE ON EVERY PAGE CHANGE ===
	$(document).on("page-change", function () {
		enforce_route();
		setTimeout(hide_sidebar, 200);
		setTimeout(add_dashboard_nav, 300);
	});

	// === ENFORCE ON INITIAL LOAD ===
	$(document).ready(function () {
		// Wait for frappe boot to be ready
		var check_count = 0;
		var check_interval = setInterval(function () {
			check_count++;
			if (check_count > 50) {
				clearInterval(check_interval);
				return;
			}
			if (frappe.boot && frappe.boot.user && frappe.boot.user.roles) {
				clearInterval(check_interval);
				if (is_branch_user()) {
					enforce_route();
					hide_sidebar();
					intercept_logo_click();
					add_dashboard_nav();
					// Redirect if on home/workspace
					var r = frappe.get_route();
					if (!r.length || r[0] === "" || r[0] === "Workspaces" ||
						r[0] === "workspaces" || r[0] === "Home" ||
						(r[0] === "Workspace" && r[1] === "Home")) {
						frappe.set_route("rmax-dashboard");
					}
				}
			}
		}, 100);
	});

	// === OVERRIDE DEFAULT HOME PAGE ===
	var _original_set_route = frappe.set_route;
	frappe.set_route = function () {
		var args = Array.prototype.slice.call(arguments);
		if (is_branch_user()) {
			var target = "";
			if (args.length === 1 && typeof args[0] === "string") {
				target = args[0].toLowerCase();
			} else if (args.length > 0 && typeof args[0] === "string") {
				target = args[0].toLowerCase();
			}
			if (target === "" || target === "home" || target === "workspace" ||
				target === "workspaces" || target === "workspace/home" ||
				target === "/" || target === "/app" || target === "/app/home") {
				args = ["rmax-dashboard"];
			}
		}
		return _original_set_route.apply(frappe, args);
	};
})();
