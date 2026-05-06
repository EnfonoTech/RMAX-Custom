/**
 * RMAX Custom: Delivery Note form.
 *
 *  - Inter-Company mode: ticking `Inter Company` restricts the customer
 *    dropdown to internal customers, locks the selling price list to
 *    "Inter Company Price", and reveals the inter-company branch picker.
 *  - Branch/Stock User: filter source warehouse + per-item warehouse
 *    to the user's Branch Configuration warehouse list.
 *  - Hide target_warehouse on the items grid for non-transfer DNs;
 *    target side isn't part of the standard outbound DN flow.
 */

const RMAX_INTER_COMPANY_PRICE_LIST = "Inter Company Price";

// ---------------------------------------------------------------------------
// Task 5.2: Client-side auto-fill of set_warehouse for Branch Users on new DNs
// ---------------------------------------------------------------------------
const RMAX_DN_WAREHOUSE_BYPASS_ROLES = [
    "Sales Manager", "System Manager", "Sales Master Manager", "Stock Manager",
];

function _rmax_dn_autofill_source_warehouse(frm) {
    if (!frm.is_new()) return;
    if (frm.doc.set_warehouse) return;
    if (frappe.session.user === "Administrator") return;
    if (RMAX_DN_WAREHOUSE_BYPASS_ROLES.some((r) => frappe.user.has_role(r))) return;

    frappe.call({
        method: "rmax_custom.branch_defaults.get_user_branch_warehouses",
        callback(r) {
            if (r.message && r.message.length && !frm.doc.set_warehouse) {
                frm.set_value("set_warehouse", r.message[0]);
            }
        },
    });
}

const RMAX_BRANCH_RESTRICTED_ROLES = ["Branch User", "Stock User"];
const RMAX_BRANCH_OVERRIDE_ROLES = [
    "System Manager",
    "Stock Manager",
    "Sales Manager",
    "Sales Master Manager",
    "Administrator",
];

function _rmax_dn_is_branch_restricted() {
    if (frappe.session.user === "Administrator") return false;
    const roles = frappe.user_roles || [];
    if (RMAX_BRANCH_OVERRIDE_ROLES.some((r) => roles.includes(r))) return false;
    return RMAX_BRANCH_RESTRICTED_ROLES.some((r) => roles.includes(r));
}

let _rmax_dn_branch_warehouses_cache = null;

function _rmax_dn_load_branch_warehouses(callback) {
    if (_rmax_dn_branch_warehouses_cache !== null) {
        callback(_rmax_dn_branch_warehouses_cache);
        return;
    }
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "User Permission",
            filters: { user: frappe.session.user, allow: "Warehouse" },
            fields: ["for_value"],
            limit_page_length: 200,
        },
        callback: function (r) {
            const list = (r.message || []).map((row) => row.for_value).filter(Boolean);
            _rmax_dn_branch_warehouses_cache = list;
            callback(list);
        },
    });
}

frappe.ui.form.on("Delivery Note", {
    onload: function (frm) {
        _rmax_apply_inter_company_mode(frm);
        _rmax_dn_apply_warehouse_query(frm);
    },
    refresh: function (frm) {
        _rmax_apply_inter_company_mode(frm);
        _rmax_dn_apply_warehouse_query(frm);
        _rmax_dn_hide_target_warehouse(frm);
        // Re-hide after the grid finishes its first render.
        setTimeout(() => _rmax_dn_hide_target_warehouse(frm), 250);
        // Auto-fill set_warehouse from the user's branch config for new DNs.
        _rmax_dn_autofill_source_warehouse(frm);
    },
    items_on_form_rendered: function (frm) {
        _rmax_dn_hide_target_warehouse(frm);
    },
    is_internal_customer: function (frm) {
        _rmax_dn_hide_target_warehouse(frm);
    },
    custom_is_inter_company: function (frm) {
        _rmax_apply_inter_company_mode(frm);

        if (frm.doc.custom_is_inter_company) {
            frm.set_value("selling_price_list", RMAX_INTER_COMPANY_PRICE_LIST);
            // Clear a non-internal customer that was already picked
            if (frm.doc.customer) {
                frappe.db
                    .get_value("Customer", frm.doc.customer, "is_internal_customer")
                    .then((r) => {
                        if (!(r.message && r.message.is_internal_customer)) {
                            frm.set_value("customer", "");
                        }
                    });
            }
        } else {
            // Clear the inter-company branch picker so a stale value doesn't
            // get carried forward.
            if (frm.doc.custom_inter_company_branch) {
                frm.set_value("custom_inter_company_branch", null);
            }
        }
    },
});

function _rmax_dn_apply_warehouse_query(frm) {
    if (!_rmax_dn_is_branch_restricted()) return;

    _rmax_dn_load_branch_warehouses(function (allowed) {
        if (!allowed.length) return;

        const filter_fn = function () {
            return {
                filters: {
                    name: ["in", allowed],
                    is_group: 0,
                },
                ignore_user_permissions: 1,
            };
        };

        frm.set_query("set_warehouse", filter_fn);
        frm.set_query("warehouse", "items", filter_fn);
    });
}

function _rmax_dn_hide_target_warehouse(frm) {
    // target_warehouse on Delivery Note Item only matters when the DN is
    // a stock-transfer style document. Hide it on the standard outbound
    // grid so operators aren't asked for it. Branch/Stock Users always
    // see source-only.
    const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
    if (!grid) return;

    // DN doesn't have is_internal_supplier_invoice; the equivalent flag is
    // is_internal_customer (via the Customer master). Hide target_warehouse
    // for branch users always, and for everyone else unless this DN is the
    // inter-company / internal-customer flow.
    const is_internal = !!frm.doc.is_internal_customer;
    const should_hide = _rmax_dn_is_branch_restricted() || !is_internal;

    // Also hide the header-level Set Target Warehouse field.
    if (frm.set_df_property) {
        frm.set_df_property("set_target_warehouse", "hidden", should_hide ? 1 : 0);
        frm.set_df_property("set_target_warehouse", "reqd", 0);
        if (frm.fields_dict.set_target_warehouse) {
            try {
                frm.toggle_display("set_target_warehouse", !should_hide);
            } catch (e) {}
        }
    }

    try {
        // 1) Mutate the in-memory DocField so any subsequent render uses it.
        const df = frappe.meta.get_docfield("Delivery Note Item", "target_warehouse", frm.doc.name);
        if (df) {
            df.hidden = should_hide ? 1 : 0;
            df.in_list_view = should_hide ? 0 : df.in_list_view;
            df.reqd = 0;
        }
        // 2) v15 grid.toggle_display reliably hides the grid column header.
        if (grid.toggle_display) {
            grid.toggle_display("target_warehouse", !should_hide);
        }
        // 3) Belt-and-suspenders: flip via update_docfield_property too.
        if (grid.update_docfield_property) {
            grid.update_docfield_property("target_warehouse", "hidden", should_hide ? 1 : 0);
            grid.update_docfield_property("target_warehouse", "reqd", 0);
            grid.update_docfield_property("target_warehouse", "in_list_view", should_hide ? 0 : 1);
        }
        // 4) Force the visible_columns cache to recompute.
        if (grid.visible_columns) grid.visible_columns = undefined;
        grid.refresh();
    } catch (e) {
        // grid may not be mounted yet on the very first refresh
    }
}

function _rmax_apply_inter_company_mode(frm) {
    const on = !!frm.doc.custom_is_inter_company;

    // Customer query: only internal customers when mode is on
    frm.set_query("customer", function () {
        if (on) {
            return { filters: { is_internal_customer: 1 } };
        }
        return {};
    });

    // Price list lock
    frm.set_df_property("selling_price_list", "read_only", on ? 1 : 0);
    if (on && frm.is_new() && !frm.doc.selling_price_list) {
        frm.set_value("selling_price_list", RMAX_INTER_COMPANY_PRICE_LIST);
    }

    // Hide the "+ Create new Customer" button next to the Link field in
    // inter-company mode — operators must pick an existing internal
    // Customer, never create a fresh one here.
    const $wrapper = frm.fields_dict.customer && frm.fields_dict.customer.$wrapper;
    if ($wrapper) {
        const $btn = $wrapper.find(".btn-new, .link-btn");
        if (on) {
            $btn.hide();
        } else {
            $btn.show();
        }
    }
    if (frm.fields_dict.customer) {
        // Newer Frappe versions respect only_select on the dataframe
        frm.fields_dict.customer.df.only_select = on ? 1 : 0;
    }
}
