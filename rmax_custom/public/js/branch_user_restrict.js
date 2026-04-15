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
		if (frappe.boot && frappe.boot.user && frappe.boot.user.roles) {
			var roles = frappe.boot.user.roles;
			if (roles.indexOf("System Manager") !== -1) return false;
			if (roles.indexOf("Administrator") !== -1) return false;
			if (roles.indexOf("Stock Manager") !== -1) return false;
			if (roles.indexOf("Branch User") !== -1) return true;
		}
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
		if (!is_branch_user()) return;
		var route = frappe.get_route();

		// Redirect home-like routes to dashboard
		var first = (route[0] || "").toLowerCase();
		if (!route.length || first === "" || first === "workspaces" ||
			first === "home" || first === "workspace" ||
			(first === "workspace" && (route[1] || "").toLowerCase() === "home") ||
			(first === "workspace" && (route[1] || "").toLowerCase() === "branch user")) {
			frappe.set_route("rmax-dashboard");
			return;
		}

		if (!is_route_allowed(route)) {
			frappe.set_route("rmax-dashboard");
		}
	}

	function hide_sidebar() {
		if (!is_branch_user()) return;

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
		if (!is_branch_user()) return;

		$(".navbar-brand, .navbar-home").each(function () {
			var $el = $(this);
			// Change href so Frappe's router reads correct pathname on click
			if ($el.attr("href") !== "/app/rmax-dashboard") {
				$el.attr("href", "/app/rmax-dashboard");
			}
			// Also bind a direct click handler as fallback
			if (!$el.data("rmax-bound")) {
				$el.data("rmax-bound", true);
				$el.on("click", function (e) {
					if (!is_branch_user()) return;
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
		if (!is_branch_user()) return;
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

	// === APPLY ALL RESTRICTIONS ===
	function apply_all() {
		if (!is_branch_user()) return;
		enforce_route();
		hide_sidebar();
		fix_logo_href();
		add_dashboard_nav();
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
				if (is_branch_user()) {
					apply_all();

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

	// Keep polling to fix the logo and add button
	// Navbar is rendered async by Frappe, so we need to keep checking
	setInterval(function () {
		if (is_branch_user()) {
			fix_logo_href();
			add_dashboard_nav();
		}
	}, 1000);

})();
