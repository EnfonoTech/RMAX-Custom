frappe.ui.form.on("Delivery Return", {
	refresh: function (frm) {
		frm.fields_dict.items.grid.get_field("against_delivery_note").get_query = function () {
			return {
				filters: {
					customer: frm.doc.customer || "",
					docstatus: 1,
					is_return: 0,
					company: frm.doc.company || ""
				}
			};
		};

		// Show links to created return DNs after submit
		if (frm.doc.created_return_dns && frm.doc.docstatus === 1) {
			const names = frm.doc.created_return_dns.split(",").map(s => s.trim()).filter(Boolean);
			names.forEach(function (name) {
				frm.add_custom_button(name, function () {
					frappe.set_route("Form", "Delivery Note", name);
				}, __("Return DNs"));
			});
		}
	},

	customer: function (frm) {
		// Clear DN references when customer changes
		(frm.doc.items || []).forEach(function (row) {
			frappe.model.set_value(row.doctype, row.name, "against_delivery_note", "");
			frappe.model.set_value(row.doctype, row.name, "returnable_qty", 0);
			frappe.model.set_value(row.doctype, row.name, "rate", 0);
			frappe.model.set_value(row.doctype, row.name, "amount", 0);
		});
	},
});

frappe.ui.form.on("Delivery Return Item", {
	item_code: function (frm, cdt, cdn) {
		_dr_fetch_source_dn(frm, cdt, cdn);
	},

	against_delivery_note: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.against_delivery_note || !row.item_code) return;

		frappe.call({
			method: "rmax_custom.api.delivery_note.validate_return_against_dn",
			args: {
				source_dn: row.against_delivery_note,
				customer: frm.doc.customer,
				items: JSON.stringify([{ item_code: row.item_code, qty: flt(row.qty) || 1 }])
			},
			callback: function (r) {
				const res = r.message || {};
				if (res.valid && res.items && res.items.length) {
					const info = res.items[0];
					frappe.model.set_value(cdt, cdn, "rate", info.rate);
					frappe.model.set_value(cdt, cdn, "returnable_qty", info.qty);
					frappe.model.set_value(cdt, cdn, "uom", info.uom);
				} else if (!res.valid) {
					frappe.show_alert({ message: (res.errors || []).join("<br>"), indicator: "red" }, 5);
					frappe.model.set_value(cdt, cdn, "against_delivery_note", "");
				}
			}
		});
	},

	qty: function (frm, cdt, cdn) {
		_dr_calc_amount(cdt, cdn);
	},

	rate: function (frm, cdt, cdn) {
		_dr_calc_amount(cdt, cdn);
	},
});

function _dr_fetch_source_dn(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.item_code || !frm.doc.customer || !frm.doc.company) return;

	frappe.call({
		method: "rmax_custom.api.delivery_note.get_return_source_dn",
		args: {
			customer: frm.doc.customer,
			company: frm.doc.company,
			item_code: row.item_code,
			qty: flt(row.qty) || 1
		},
		callback: function (r) {
			if (r.message) {
				const info = r.message;
				frappe.model.set_value(cdt, cdn, "against_delivery_note", info.dn);
				frappe.model.set_value(cdt, cdn, "rate", info.rate);
				frappe.model.set_value(cdt, cdn, "uom", info.uom);
				frappe.model.set_value(cdt, cdn, "returnable_qty", info.returnable_qty);
			} else {
				frappe.show_alert({
					message: __("No returnable Delivery Note found for {0} under this customer.", [row.item_code]),
					indicator: "orange"
				}, 5);
			}
		}
	});
}

function _dr_calc_amount(cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
}
