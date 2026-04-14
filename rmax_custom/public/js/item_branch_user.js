/**
 * RMAX Custom: Item form restrictions for Branch User
 *
 * Branch Users can VIEW items but:
 * - Cannot see cost/valuation fields
 * - Cannot see inter-company price lists
 * - Cannot create or edit items
 */

frappe.ui.form.on("Item", {
	refresh: function (frm) {
		if (!_is_branch_user_only()) return;

		// Hide cost and valuation fields
		var cost_fields = [
			"valuation_rate",
			"valuation_method",
			"last_purchase_rate",
			"standard_rate",
			"opening_stock",
			"standard_selling_rate",
		];

		cost_fields.forEach(function (field) {
			if (frm.fields_dict[field]) {
				frm.set_df_property(field, "hidden", 1);
			}
		});

		// Hide the "Add Row" button on Item Price if it exists
		if (frm.fields_dict.item_defaults) {
			// Make item defaults read-only
			frm.set_df_property("item_defaults", "read_only", 1);
		}
	},

	onload: function (frm) {
		if (!_is_branch_user_only()) return;

		// Filter Price List to exclude inter-company price lists
		frm.set_query("price_list", function () {
			return {
				filters: {
					selling: 1,
				},
			};
		});
	},
});

/**
 * Check if user has Branch User role but NOT Stock Manager or System Manager.
 * Stock Managers and System Managers should see everything.
 */
function _is_branch_user_only() {
	var roles = frappe.user_roles || [];
	if (roles.includes("System Manager") || roles.includes("Stock Manager")) {
		return false;
	}
	return roles.includes("Branch User");
}
