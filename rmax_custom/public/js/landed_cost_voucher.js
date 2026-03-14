// Copyright (c) 2025, Rmax Custom
// Landed Cost Voucher: "Distribute by CBM" when Distribute Manually - distribute by custom_cbm ratio

frappe.ui.form.on("Landed Cost Voucher", {
	refresh: function (frm) {
		// Patch form controller to run CBM distribution when Distribute Manually + Distribute by CBM
		var form_script = frm.page.script_manager && frm.page.script_manager.form_script;
		if (form_script && !form_script._rmax_cbm_patched) {
			form_script._rmax_cbm_patched = true;
			var original_set_applicable = form_script.set_applicable_charges_for_item;
			if (original_set_applicable) {
				form_script.set_applicable_charges_for_item = function () {
					var me = this;
					if (
						me.frm.doc.distribute_charges_based_on === "Distribute Manually" &&
						me.frm.doc.custom_distribute_by_cbm
					) {
						rmax_set_applicable_charges_by_cbm(me.frm);
						return;
					}
					return original_set_applicable.apply(this, arguments);
				};
			}
		}
	},
	custom_distribute_by_cbm: function (frm) {
		if (frm.doc.custom_distribute_by_cbm) {
			rmax_set_applicable_charges_by_cbm(frm);
		}
	},
	distribute_charges_based_on: function (frm) {
		if (frm.doc.distribute_charges_based_on !== "Distribute Manually" && frm.doc.custom_distribute_by_cbm) {
			frm.set_value("custom_distribute_by_cbm", 0);
		}
	},
});

function rmax_set_applicable_charges_by_cbm(frm) {
	if (!frm.doc.taxes || !frm.doc.taxes.length || !frm.doc.items || !frm.doc.items.length) {
		return;
	}
	var total_cbm = 0;
	$.each(frm.doc.items, function (i, d) {
		total_cbm += flt(d.custom_cbm);
	});
	total_cbm = flt(total_cbm);
	var total_charges = 0;
	var prec = 2;
	try {
		var first_row = frm.doc.items[0];
		if (first_row && typeof precision === "function") {
			var p = precision("applicable_charges", first_row);
			if (p !== undefined && !isNaN(p)) prec = p;
		}
	} catch (e) {}

	if (!total_cbm || total_cbm <= 0) {
		$.each(frm.doc.items, function (i, item) {
			item.applicable_charges = 0;
		});
		refresh_field("items");
		return;
	}

	$.each(frm.doc.items, function (i, item) {
		var ratio = flt(item.custom_cbm) / total_cbm;
		var charge = flt(ratio * flt(frm.doc.total_taxes_and_charges), prec);
		item.applicable_charges = charge !== undefined && !isNaN(charge) ? charge : 0;
		total_charges += item.applicable_charges;
	});
	var diff = flt(frm.doc.total_taxes_and_charges) - flt(total_charges);
	if (diff && frm.doc.items.length) {
		var last = frm.doc.items[frm.doc.items.length - 1];
		last.applicable_charges = flt(last.applicable_charges) + diff;
	}
	refresh_field("items");
}

frappe.ui.form.on("Landed Cost Item", {
	custom_cbm: function (frm) {
		if (
			frm.doc.distribute_charges_based_on === "Distribute Manually" &&
			frm.doc.custom_distribute_by_cbm
		) {
			rmax_set_applicable_charges_by_cbm(frm);
		}
	},
});

// When tax amount changes, recalc total_taxes_and_charges and redistribute (so applicable_charges update)
frappe.ui.form.on("Landed Cost Taxes and Charges", {
	amount: function (frm) {
		rmax_on_taxes_changed(frm);
	},
	base_amount: function (frm) {
		rmax_on_taxes_changed(frm);
	},
});

function rmax_on_taxes_changed(frm) {
	// Recalc total from taxes table
	var form_script = frm.page.script_manager && frm.page.script_manager.form_script;
	if (form_script && form_script.set_total_taxes_and_charges) {
		form_script.set_total_taxes_and_charges();
	}
	if (
		frm.doc.distribute_charges_based_on === "Distribute Manually" &&
		frm.doc.custom_distribute_by_cbm
	) {
		rmax_set_applicable_charges_by_cbm(frm);
	}
}
