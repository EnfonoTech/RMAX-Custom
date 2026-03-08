frappe.ui.form.on("Sales Invoice", {
	onload: function (frm) {
		frm.set_query("inter_company_branch", function () {
			if (!frm.doc.represents_company) {
				return { filters: { name: "" } };
			}
			return {
				query: "rmax_custom.rmax_custom.doctype.inter_company_branch.inter_company_branch.get_branches_for_company",
				filters: { company: frm.doc.represents_company },
			};
		});
	},
});
