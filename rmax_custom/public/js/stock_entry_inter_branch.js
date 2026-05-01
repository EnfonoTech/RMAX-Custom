/**
 * Surface inter-branch companion Journal Entry on the Stock Entry form.
 *
 * Phase 2 of the Inter-Branch R/P module creates a Journal Entry whose
 * `custom_source_doctype = "Stock Entry"` and `custom_source_docname = SE.name`
 * (stamped on Journal Entry Account child rows). Frappe's standard dashboard
 * cannot follow that via-child-table link, so we render it ourselves:
 *
 *   1. A custom button under the SE form: "View Inter-Branch JE: ACC-JV-..."
 *   2. A connection card in the sidebar (Frappe-style) listing each linked JE.
 *
 * Triggers only on submitted Stock Entries with purpose = Material Transfer
 * (the only purpose the inter-branch hook acts on).
 */
frappe.ui.form.on("Stock Entry", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.purpose !== "Material Transfer") return;

		frappe.db
			.get_list("Journal Entry Account", {
				filters: {
					custom_source_doctype: "Stock Entry",
					custom_source_docname: frm.doc.name,
					docstatus: 1,
				},
				fields: ["parent"],
				limit: 20,
			})
			.then((rows) => {
				const je_names = [...new Set(rows.map((r) => r.parent))];
				if (!je_names.length) return;

				// Custom button(s) — one per linked JE
				je_names.forEach((je) => {
					frm.add_custom_button(
						je,
						() => frappe.set_route("Form", "Journal Entry", je),
						__("Inter-Branch JE")
					);
				});

				// Sidebar connection card — append to existing connections area
				render_inter_branch_sidebar(frm, je_names);
			});
	},
});

function render_inter_branch_sidebar(frm, je_names) {
	if (!frm.sidebar || !frm.sidebar.sidebar) return;

	// Remove any prior render so toggling between docs doesn't stack cards
	frm.sidebar.sidebar.find(".rmax-inter-branch-card").remove();

	const $card = $(`
		<div class="form-group rmax-inter-branch-card" style="margin-top: 12px;">
			<div class="text-muted small" style="margin-bottom: 4px; font-weight: 600;">
				${__("Inter-Branch")}
			</div>
		</div>
	`);

	je_names.forEach((je) => {
		const $link = $(`
			<a class="badge badge-info" style="margin-right: 4px; margin-bottom: 4px;
			    display: inline-block; cursor: pointer; padding: 4px 8px;">
				${frappe.utils.escape_html(je)}
			</a>
		`);
		$link.on("click", () => frappe.set_route("Form", "Journal Entry", je));
		$card.append($link);
	});

	frm.sidebar.sidebar.append($card);
}
