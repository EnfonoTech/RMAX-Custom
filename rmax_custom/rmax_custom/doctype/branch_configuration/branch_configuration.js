// Copyright (c) 2026, Enfono and contributors
// For license information, please see license.txt

frappe.ui.form.on("Branch Configuration", {
	refresh(frm) {
		set_child_filters(frm);
	},
	company(frm) {
		set_child_filters(frm);

		// Clear warehouse + cost center + account fields when company changes
		// (they may belong to the old company)
		if (frm.doc.warehouse && frm.doc.warehouse.length) {
			frm.clear_table("warehouse");
			frm.refresh_field("warehouse");
		}
		if (frm.doc.cost_center && frm.doc.cost_center.length) {
			frm.clear_table("cost_center");
			frm.refresh_field("cost_center");
		}
		if (frm.doc.cash_account) {
			frm.set_value("cash_account", null);
		}
		if (frm.doc.bank_account) {
			frm.set_value("bank_account", null);
		}
	}
});

function set_child_filters(frm) {
	frm.set_query("warehouse", "warehouse", function () {
		return {
			filters: {
				company: frm.doc.company,
				is_group: 0
			}
		};
	});

	frm.set_query("cost_center", "cost_center", function () {
		return {
			filters: {
				company: frm.doc.company,
				is_group: 0
			}
		};
	});

	frm.set_query("cash_account", function () {
		return {
			filters: {
				company: frm.doc.company,
				account_type: "Cash",
				is_group: 0
			}
		};
	});

	frm.set_query("bank_account", function () {
		return {
			filters: {
				company: frm.doc.company,
				account_type: "Bank",
				is_group: 0
			}
		};
	});
}
