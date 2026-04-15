/**
 * RMAX: Branch User Access Restriction
 *
 * Branch Users can ONLY access:
 * - rmax-dashboard (home page)
 * - Sales Invoice, Quotation, Customer, Payment Entry
 * - Purchase Receipt, Purchase Invoice
 * - Material Request, Stock Transfer
 * - Item, Item Price
 * - Reports: Stock Sales Report, Collection Report, Stock Balance, Stock Ledger, General Ledger
 * - Their own User profile
 *
 * Everything else is blocked and redirected to dashboard.
 */
(function () {
	"use strict";

	// Only restrict Branch Users (not admins)
	if (
		!frappe.user_roles ||
		!frappe.user_roles.includes("Branch User") ||
		frappe.user_roles.includes("System Manager") ||
		frappe.user_roles.includes("Administrator") ||
		frappe.user_roles.includes("Stock Manager")
	) {
		return;
	}

	// Allowed DocTypes for Branch User
	var ALLOWED_DOCTYPES = [
		"Sales Invoice",
		"Quotation",
		"Customer",
		"Payment Entry",
		"Purchase Receipt",
		"Purchase Invoice",
		"Material Request",
		"Stock Transfer",
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

	// Allowed report names
	var ALLOWED_REPORTS = [
		"Stock Sales Report",
		"Collection Report",
		"Stock Balance",
		"Stock Ledger",
		"General Ledger",
	];

	// Allowed page routes
	var ALLOWED_PAGES = [
		"rmax-dashboard",
		"user-guide",
		"print",
		"user",
	];

	function is_route_allowed(route) {
		if (!route || !route.length) return true;

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

		// Allow app/doctype patterns (URL style)
		if (first === "app") {
			var slug = (second || "").replace(/-/g, " ");
			// Check if it maps to an allowed doctype
			for (var m = 0; m < ALLOWED_DOCTYPES.length; m++) {
				if (slug.toLowerCase() === ALLOWED_DOCTYPES[m].toLowerCase()) return true;
			}
			// Check allowed pages
			for (var n = 0; n < ALLOWED_PAGES.length; n++) {
				if (second === ALLOWED_PAGES[n]) return true;
			}
			// Allow query-report under app
			if (second === "query-report" && route[2]) {
				for (var p = 0; p < ALLOWED_REPORTS.length; p++) {
					if (route[2] === ALLOWED_REPORTS[p]) return true;
				}
			}
			return false;
		}

		// Block workspace, module, setup pages
		if (first === "workspace" || first === "modules" || first === "setup-wizard") {
			return false;
		}

		// Block everything else by default
		return false;
	}

	// Intercept route changes
	$(document).on("page-change", function () {
		var route = frappe.get_route();
		if (!is_route_allowed(route)) {
			frappe.set_route("rmax-dashboard");
		}
	});

	// Hide sidebar modules that Branch User shouldn't see
	frappe.after_ajax(function () {
		_hide_sidebar_items();
	});

	$(document).on("page-change", function () {
		setTimeout(_hide_sidebar_items, 300);
	});

	function _hide_sidebar_items() {
		// Hide the main sidebar/module links
		$(".desk-sidebar .sidebar-menu a").each(function () {
			var href = $(this).attr("href") || "";
			var text = $(this).text().trim();

			// Keep only relevant modules
			var keep = false;
			var allowed_modules = [
				"rmax-dashboard", "selling", "buying", "stock",
				"accounts", "assets"
			];

			for (var i = 0; i < allowed_modules.length; i++) {
				if (href.toLowerCase().indexOf(allowed_modules[i]) !== -1) {
					keep = true;
					break;
				}
			}

			// Hide HR, Manufacturing, Settings, etc.
			if (!keep && text) {
				var hide_keywords = [
					"HR", "Payroll", "Manufacturing", "Projects",
					"Website", "Settings", "Integrations", "Users",
					"Customization", "CRM", "Support", "Quality",
					"Education", "Healthcare", "Agriculture", "Non Profit",
					"Utilities", "ERPNext Settings", "Setup", "Build",
					"Getting Started"
				];
				for (var j = 0; j < hide_keywords.length; j++) {
					if (text.indexOf(hide_keywords[j]) !== -1) {
						$(this).closest("li, .sidebar-item").hide();
						return;
					}
				}
			}
		});
	}
})();
