// rmax_custom: Payment Entry — make Branch mandatory and surface it prominently
frappe.ui.form.on("Payment Entry", {
	setup: function (frm) {
		// Make branch required at field-definition level (fires before render)
		if (frm.fields_dict && frm.fields_dict.branch) {
			frm.fields_dict.branch.df.reqd = 1;
		}
	},

	refresh: function (frm) {
		_rmax_pe_highlight_branch(frm);
	},

	onload: function (frm) {
		_rmax_pe_highlight_branch(frm);
	},
});

function _rmax_pe_highlight_branch(frm) {
	if (!frm.fields_dict || !frm.fields_dict.branch) return;

	// Mark required regardless of docstatus
	frm.set_df_property("branch", "reqd", 1);

	// Move branch field to the top — insert after posting_date in the DOM
	// by prepending the wrapper into the first section's column
	const $branch_wrapper = frm.fields_dict.branch.$wrapper;
	if (!$branch_wrapper || !$branch_wrapper.length) return;

	// Only reposition once to avoid infinite refresh loops
	if ($branch_wrapper.data("rmax_repositioned")) return;

	// Find the first form section to prepend branch into
	const $first_col = frm.layout
		? frm.layout.sections[0]?.$columns?.[0]
		: null;

	if ($first_col && $first_col.length) {
		$branch_wrapper.detach().prependTo($first_col);
		$branch_wrapper.data("rmax_repositioned", true);
	}

	// Highlight if empty
	if (!frm.doc.branch) {
		$branch_wrapper
			.find(".control-label")
			.css({ color: "var(--red-600, #e53e3e)", "font-weight": "bold" });
	}
}
