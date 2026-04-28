// Copyright (c) 2026, Enfono Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("BNPL Settlement", {
	refresh: function (frm) {
		if (frm.doc.docstatus === 1 && frm.doc.journal_entry) {
			frm.add_custom_button(__("View Journal Entry"), function () {
				frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry);
			});
		}
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fetch Pending Invoices"), function () {
				_rmax_fetch_pending_invoices(frm);
			});
		}
	},

	mode_of_payment: function (frm) {
		if (!frm.doc.mode_of_payment) return;
		frappe.db
			.get_value("Mode of Payment", frm.doc.mode_of_payment, [
				"custom_bnpl_clearing_account",
				"custom_surcharge_percentage",
			])
			.then(function (r) {
				const v = (r && r.message) || {};
				if (v.custom_bnpl_clearing_account && !frm.doc.clearing_account) {
					frm.set_value("clearing_account", v.custom_bnpl_clearing_account);
				}
				if (!flt(v.custom_surcharge_percentage)) {
					frappe.msgprint({
						title: __("Not a BNPL Mode of Payment"),
						message: __(
							"This Mode of Payment has no Surcharge Percentage configured. " +
								"Set Surcharge Percentage on Tabby/Tamara before using BNPL Settlement."
						),
						indicator: "orange",
					});
				}
			});
	},

	company: function (frm) {
		if (!frm.doc.company) return;
		frappe.db
			.get_value("Company", frm.doc.company, "custom_bnpl_fee_account")
			.then(function (r) {
				const v = (r && r.message) || {};
				if (v.custom_bnpl_fee_account && !frm.doc.fee_account) {
					frm.set_value("fee_account", v.custom_bnpl_fee_account);
				}
			});
	},

	fee_amount: function (frm) {
		_rmax_recalc_net(frm);
	},

	gross_amount: function (frm) {
		_rmax_recalc_net(frm);
	},

	onload: function (frm) {
		frm.set_query("clearing_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					account_type: ["in", ["Bank", "Cash", ""]],
				},
			};
		});
		frm.set_query("bank_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					account_type: ["in", ["Bank", "Cash"]],
				},
			};
		});
		frm.set_query("fee_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					root_type: "Expense",
				},
			};
		});
		frm.set_query("mode_of_payment", function () {
			return {
				filters: {
					custom_surcharge_percentage: [">", 0],
				},
			};
		});
	},
});

frappe.ui.form.on("BNPL Settlement Invoice", {
	allocated_amount: function (frm) {
		_rmax_recalc_gross(frm);
	},
	invoices_remove: function (frm) {
		_rmax_recalc_gross(frm);
	},
});

function _rmax_recalc_gross(frm) {
	const gross = (frm.doc.invoices || []).reduce(function (s, r) {
		return s + flt(r.allocated_amount);
	}, 0);
	frm.set_value("gross_amount", gross);
	_rmax_recalc_net(frm);
}

function _rmax_recalc_net(frm) {
	const net = flt(frm.doc.gross_amount) - flt(frm.doc.fee_amount);
	if (Math.abs(flt(frm.doc.net_amount) - net) > 0.001) {
		frm.set_value("net_amount", net);
	}
}

function _rmax_fetch_pending_invoices(frm) {
	if (!frm.doc.company || !frm.doc.mode_of_payment) {
		frappe.msgprint(__("Set Company and Mode of Payment first."));
		return;
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Fetch Pending Invoices"),
		fields: [
			{
				fieldname: "to_date",
				label: __("Up To Posting Date"),
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
			},
		],
		primary_action_label: __("Fetch"),
		primary_action: function (values) {
			frappe.call({
				method:
					"rmax_custom.rmax_custom.doctype.bnpl_settlement.bnpl_settlement.get_pending_invoices",
				args: {
					company: frm.doc.company,
					mode_of_payment: frm.doc.mode_of_payment,
					to_date: values.to_date,
				},
				callback: function (r) {
					const rows = (r && r.message) || [];
					if (!rows.length) {
						frappe.msgprint(__("No pending invoices found for this Mode of Payment."));
						return;
					}
					frm.clear_table("invoices");
					rows.forEach(function (row) {
						const child = frm.add_child("invoices");
						child.sales_invoice = row.sales_invoice;
						child.posting_date = row.posting_date;
						child.customer = row.customer;
						child.customer_name = row.customer_name;
						child.grand_total = row.grand_total;
						child.bnpl_uplift_amount = row.bnpl_uplift_amount;
						child.allocated_amount = row.allocated_amount;
					});
					frm.refresh_field("invoices");
					_rmax_recalc_gross(frm);
					dialog.hide();
				},
			});
		},
	});
	dialog.show();
}
