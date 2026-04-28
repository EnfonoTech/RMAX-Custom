/**
 * RMAX Custom: Sales Invoice Form
 *
 * 1. New SI defaults: update_stock = 1 and set_warehouse picked from the
 *    user's default Warehouse User Permission so stock movement posts
 *    against the correct warehouse automatically.
 * 2. Branch Users cannot toggle update_stock (read-only). Elevated roles
 *    (Sales Manager, Sales Master Manager, Stock Manager, System Manager)
 *    keep full control.
 * 3. Auto-negate qty on save for Credit Notes (is_return = 1).
 */

const RMAX_UPDATE_STOCK_ELEVATED_ROLES = [
    "Sales Manager",
    "Sales Master Manager",
    "Stock Manager",
    "System Manager",
];

function _rmax_is_locked_branch_user() {
    if (frappe.session.user === "Administrator") return false;
    const roles = frappe.user_roles || [];
    if (!roles.includes("Branch User")) return false;
    return !RMAX_UPDATE_STOCK_ELEVATED_ROLES.some((r) => roles.includes(r));
}

function _rmax_fetch_default_warehouse(callback) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "User Permission",
            filters: {
                user: frappe.session.user,
                allow: "Warehouse",
                is_default: 1,
            },
            fields: ["for_value"],
            limit_page_length: 1,
        },
        callback: function (r) {
            const wh =
                (r.message && r.message.length && r.message[0].for_value) || null;
            callback(wh);
        },
    });
}

frappe.ui.form.on("Sales Invoice", {
    onload: function (frm) {
        if (!frm.is_new()) return;

        if (!frm.doc.update_stock) {
            frm.set_value("update_stock", 1);
        }

        if (!frm.doc.set_warehouse) {
            _rmax_fetch_default_warehouse(function (wh) {
                if (wh && frm.is_new() && !frm.doc.set_warehouse) {
                    frm.set_value("set_warehouse", wh);
                }
            });
        }
    },
    refresh: function (frm) {
        if (_rmax_is_locked_branch_user()) {
            frm.set_df_property("update_stock", "read_only", 1);
            frm.set_df_property(
                "update_stock",
                "description",
                "Locked for Branch Users. Contact a Sales Manager to change."
            );
        }
    },
    before_save: function (frm) {
        if (!frm.doc.is_return) return;
        (frm.doc.items || []).forEach(function (row) {
            if (row.qty > 0) {
                frappe.model.set_value(row.doctype, row.name, "qty", -Math.abs(row.qty));
            }
        });
    },
});

/**
 * BNPL Surcharge Uplift (Tabby / Tamara)
 *
 * Mirrors rmax_custom.bnpl_uplift on the client so the form reflects the
 * uplifted rates in real time as the user edits the Payments table or the
 * item lines. Server-side validate hook is the source of truth — this is
 * UX only.
 */
const RMAX_BNPL_SURCHARGE_FIELD = "custom_surcharge_percentage";
const RMAX_BNPL_TOLERANCE = 0.01;
const _rmax_bnpl_surcharge_cache = {};

function _rmax_get_surcharge_pct(mode_of_payment) {
    if (!mode_of_payment) return Promise.resolve(0);
    if (Object.prototype.hasOwnProperty.call(_rmax_bnpl_surcharge_cache, mode_of_payment)) {
        return Promise.resolve(_rmax_bnpl_surcharge_cache[mode_of_payment]);
    }
    return frappe.db
        .get_value("Mode of Payment", mode_of_payment, RMAX_BNPL_SURCHARGE_FIELD)
        .then(function (r) {
            const pct = flt((r && r.message && r.message[RMAX_BNPL_SURCHARGE_FIELD]) || 0);
            _rmax_bnpl_surcharge_cache[mode_of_payment] = pct;
            return pct;
        });
}

function _rmax_compute_bnpl(frm) {
    const payments = frm.doc.payments || [];
    const total = payments.reduce(function (s, p) {
        return s + flt(p.amount);
    }, 0);
    if (total <= 0) return Promise.resolve({ ratio: 0, factor: 1 });

    const promises = payments.map(function (p) {
        return _rmax_get_surcharge_pct(p.mode_of_payment).then(function (pct) {
            return { amount: flt(p.amount), pct: pct };
        });
    });

    return Promise.all(promises).then(function (rows) {
        let bnpl_amount = 0;
        let weighted_pct_sum = 0;
        rows.forEach(function (r) {
            if (r.pct > 0) {
                bnpl_amount += r.amount;
                weighted_pct_sum += r.amount * r.pct;
            }
        });
        const ratio = total > 0 ? bnpl_amount / total : 0;
        const factor = 1 + weighted_pct_sum / total / 100;
        return { ratio: ratio, factor: factor };
    });
}

function _rmax_apply_bnpl_uplift(frm) {
    if (!frm || !frm.doc || frm.doc.doctype !== "Sales Invoice") return;
    if (frm.__rmax_bnpl_running) return;
    frm.__rmax_bnpl_running = true;

    return _rmax_compute_bnpl(frm)
        .then(function (out) {
            const ratio = out.ratio;
            const factor = out.factor;
            const items = frm.doc.items || [];

            if (ratio <= 0) {
                items.forEach(function (row) {
                    const original = flt(row.custom_original_rate);
                    if (original > 0 && Math.abs(flt(row.rate) - original) > RMAX_BNPL_TOLERANCE) {
                        frappe.model.set_value(row.doctype, row.name, "rate", original);
                    }
                    if (flt(row.custom_original_rate) !== 0) {
                        frappe.model.set_value(row.doctype, row.name, "custom_original_rate", 0);
                    }
                    if (flt(row.custom_bnpl_uplift_amount) !== 0) {
                        frappe.model.set_value(row.doctype, row.name, "custom_bnpl_uplift_amount", 0);
                    }
                });
                if (flt(frm.doc.custom_bnpl_portion_ratio) !== 0) {
                    frm.set_value("custom_bnpl_portion_ratio", 0);
                }
                return;
            }

            items.forEach(function (row) {
                const base = flt(row.custom_original_rate) || flt(row.rate);
                if (base <= 0) return;
                const new_rate = flt(base * factor, precision("rate", row));
                if (Math.abs(flt(row.custom_original_rate) - base) > RMAX_BNPL_TOLERANCE) {
                    frappe.model.set_value(row.doctype, row.name, "custom_original_rate", base);
                }
                if (Math.abs(flt(row.rate) - new_rate) > RMAX_BNPL_TOLERANCE) {
                    frappe.model.set_value(row.doctype, row.name, "rate", new_rate);
                }
                const uplift_amount = flt((new_rate - base) * flt(row.qty), precision("amount", row));
                if (Math.abs(flt(row.custom_bnpl_uplift_amount) - uplift_amount) > RMAX_BNPL_TOLERANCE) {
                    frappe.model.set_value(
                        row.doctype,
                        row.name,
                        "custom_bnpl_uplift_amount",
                        uplift_amount
                    );
                }
            });

            const ratio_pct = flt(ratio * 100, 4);
            if (Math.abs(flt(frm.doc.custom_bnpl_portion_ratio) - ratio_pct) > 0.0001) {
                frm.set_value("custom_bnpl_portion_ratio", ratio_pct);
            }
        })
        .always(function () {
            frm.__rmax_bnpl_running = false;
            frm.refresh_field("items");
            frm.refresh_field("payments");
        });
}

function _rmax_schedule_bnpl(frm) {
    if (!frm || !frm.doc || frm.doc.doctype !== "Sales Invoice") return;
    if (frm.__rmax_bnpl_pending) return;
    frm.__rmax_bnpl_pending = true;
    setTimeout(function () {
        frm.__rmax_bnpl_pending = false;
        _rmax_apply_bnpl_uplift(frm);
    }, 50);
}

frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    additional_discount_percentage: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    discount_amount: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
});

frappe.ui.form.on("Sales Invoice Payment", {
    payments_add: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    payments_remove: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    mode_of_payment: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    amount: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
});

frappe.ui.form.on("Sales Invoice Item", {
    items_add: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    items_remove: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    rate: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    qty: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    discount_percentage: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
    discount_amount: function (frm) {
        _rmax_schedule_bnpl(frm);
    },
});
