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
        // Show "Find Source DN" button for return DNs without a source linked.
        _rmax_dn_show_find_source_button(frm);
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

// ---------------------------------------------------------------------------
// DN Return — Find Source DN button
// ---------------------------------------------------------------------------

function _rmax_dn_show_find_source_button(frm) {
    // Show on any new unsaved DN without a source — user may not have set
    // is_return yet (it's read-only); we set it when they pick a source DN.
    if (frm.doc.return_against) return;
    if (!frm.is_new()) return;

    frm.add_custom_button(__("Find Source DN"), function () {
        _rmax_dn_find_source(frm);
    }, __("Return"));
}

function _rmax_dn_find_source(frm) {
    if (!frm.doc.customer) {
        frappe.msgprint(__("Please select a Customer first."));
        return;
    }

    const items = (frm.doc.items || [])
        .filter((r) => r.item_code)
        .map((r) => ({ item_code: r.item_code, qty: Math.abs(r.qty || 1) }));

    if (!items.length) {
        frappe.msgprint(__("Please add at least one item to search for the source Delivery Note."));
        return;
    }

    frappe.dom.freeze(__("Searching for matching Delivery Notes…"));

    frappe.call({
        method: "rmax_custom.api.delivery_note.find_source_delivery_notes",
        args: { customer: frm.doc.customer, items: JSON.stringify(items) },
        callback: function (r) {
            frappe.dom.unfreeze();
            const matches = r.message || [];
            if (!matches.length) {
                frappe.msgprint({
                    title: __("No Matching Delivery Notes"),
                    message: __(
                        "No submitted Delivery Note was found for customer <b>{0}</b> "
                        + "containing the entered items with returnable quantity.",
                        [frm.doc.customer]
                    ),
                    indicator: "orange",
                });
                return;
            }
            _rmax_dn_show_source_picker(frm, matches);
        },
        error: function () {
            frappe.dom.unfreeze();
        },
    });
}

function _rmax_dn_show_source_picker(frm, matches) {
    // Build a dialog that shows candidate DNs with their matched items.
    let selected_dn = null;

    const rows_html = matches.map((dn) => {
        const items_list = dn.items
            .map((i) =>
                `<li>${frappe.utils.escape_html(i.item_code)} — `
                + `${__("Returnable")}: <b>${frappe.format(i.returnable_qty, { fieldtype: "Float" })} ${frappe.utils.escape_html(i.uom)}</b></li>`
            )
            .join("");

        return `
            <div class="rmax-dn-pick-row" data-dn="${frappe.utils.escape_html(dn.name)}"
                 style="border:1px solid var(--border-color); border-radius:6px;
                        padding:12px 14px; margin-bottom:8px; cursor:pointer;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong>${frappe.utils.escape_html(dn.name)}</strong>
                    <span class="indicator-pill blue">${dn.score} ${__("item(s) matched")}</span>
                </div>
                <div style="color:var(--text-muted); font-size:12px; margin:4px 0 6px;">
                    ${frappe.format(dn.posting_date, { fieldtype: "Date" })}
                </div>
                <ul style="margin:0; padding-left:18px; font-size:12px;">${items_list}</ul>
            </div>`;
    }).join("");

    const d = new frappe.ui.Dialog({
        title: __("Select Source Delivery Note"),
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "dn_list_html",
                options: `<div id="rmax-dn-pick-list">${rows_html}</div>`,
            },
        ],
        primary_action_label: __("Apply"),
        primary_action: function () {
            if (!selected_dn) {
                frappe.msgprint(__("Please select a Delivery Note."));
                return;
            }
            d.hide();
            _rmax_dn_apply_source(frm, selected_dn);
        },
    });

    d.show();

    // Row click → highlight selection
    d.$wrapper.find("#rmax-dn-pick-list").on("click", ".rmax-dn-pick-row", function () {
        d.$wrapper.find(".rmax-dn-pick-row").css({
            "background": "",
            "border-color": "var(--border-color)",
        });
        $(this).css({
            "background": "var(--highlight-color, #f0f4ff)",
            "border-color": "var(--primary)",
        });
        selected_dn = $(this).data("dn");
    });
}

function _rmax_dn_apply_source(frm, dn_name) {
    // is_return is read-only on the form widget — write directly to frm.doc
    // to bypass the lock, then set return_against through the normal setter
    // so ERPNext's onchange logic fires correctly.
    frm.doc.is_return = 1;
    frm.refresh_field("is_return");

    frm.set_value("return_against", dn_name).then(function () {
        frappe.show_alert({
            message: __("Source Delivery Note set to {0}. Save the form to proceed.", [dn_name]),
            indicator: "green",
        });
        frm.remove_custom_button(__("Find Source DN"), __("Return"));
    });
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
