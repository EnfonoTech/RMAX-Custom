// rmax_custom: Load BNPL Settlement template into Journal Entry accounts table.
//
// Adds a "Load BNPL Settlement" button to draft Journal Entries (visible to
// Accounts User / Accounts Manager / System Manager). The dialog lets the
// operator pick a BNPL Mode of Payment + a Bank Account, then clears the
// JE accounts table and inserts three rows:
//
//   1. Dr Bank Account (operator fills the amount)
//   2. Dr BNPL Fee Expense - <abbr> (operator fills the amount)
//   3. Cr Clearing Account (operator fills, typically row1 + row2)
//
// The clearing account is resolved from `Mode of Payment Account` for the
// (Mode of Payment, Company) pair via the rmax_custom.api.bnpl whitelisted
// endpoints. Live clearing-account balance is shown in the dialog.
//
// Server-side soft-warn (rmax_custom.bnpl_clearing_guard.warn_bnpl_clearing_overdraw)
// fires on JE validate if the total credit to a clearing account exceeds its
// live balance — message-only, never blocks save / submit.
frappe.ui.form.on("Journal Entry", {
    refresh: function (frm) {
        if (frm._rmax_bnpl_btn) return;
        if (frm.doc.docstatus !== 0) return;
        if (!["Journal Entry", "Bank Entry"].includes(frm.doc.voucher_type)) return;

        const allowed = ["Accounts User", "Accounts Manager", "System Manager"];
        if (!frappe.user_roles.some((r) => allowed.includes(r))) return;

        frm.add_custom_button(__("Load BNPL Settlement"), function () {
            rmax_show_bnpl_settlement_dialog(frm);
        });
        frm._rmax_bnpl_btn = true;
    },
});

function rmax_show_bnpl_settlement_dialog(frm) {
    if (!frm.doc.company) {
        frappe.msgprint(__("Pick a Company first."));
        return;
    }

    const d = new frappe.ui.Dialog({
        title: __("Load BNPL Settlement"),
        fields: [
            {
                fieldname: "mop",
                fieldtype: "Link",
                label: __("Mode of Payment"),
                options: "Mode of Payment",
                reqd: 1,
                get_query: function () {
                    return {
                        filters: { custom_surcharge_percentage: [">", 0] },
                    };
                },
                onchange: function () {
                    rmax_refresh_clearing_info(d, frm);
                },
            },
            {
                fieldname: "bank_account",
                fieldtype: "Link",
                label: __("Bank Account"),
                options: "Account",
                reqd: 1,
                get_query: function () {
                    return {
                        filters: {
                            company: frm.doc.company,
                            is_group: 0,
                            account_type: ["in", ["Bank", "Cash"]],
                        },
                    };
                },
            },
            { fieldtype: "Section Break" },
            {
                fieldname: "clearing_info",
                fieldtype: "HTML",
                label: __("Clearing Account Info"),
            },
        ],
        primary_action_label: __("Load Heads"),
        primary_action: function (vals) {
            rmax_load_bnpl_heads(frm, d, vals);
        },
    });
    d.show();
}

function rmax_refresh_clearing_info(d, frm) {
    const mop = d.get_value("mop");
    const $info = d.fields_dict.clearing_info.$wrapper;
    if (!mop) {
        $info.html("");
        return;
    }
    frappe.call({
        method: "rmax_custom.api.bnpl.get_clearing_account_for_mop",
        args: { mop: mop, company: frm.doc.company },
        callback: function (r) {
            const res = r.message || {};
            if (!res.account) {
                $info.html(
                    `<div style="color:#b54708;">${__(
                        "No clearing account configured for {0} on {1}. Configure Mode of Payment Account first.",
                        [mop, frm.doc.company]
                    )}</div>`
                );
                return;
            }
            frappe.call({
                method: "rmax_custom.api.bnpl.get_clearing_balance",
                args: { account: res.account },
                callback: function (r2) {
                    const bal = (r2.message || 0).toFixed(2);
                    $info.html(
                        `<div>
                            <strong>${__("Clearing Account")}:</strong> ${frappe.utils.escape_html(res.account)}<br>
                            <strong>${__("Currency")}:</strong> ${frappe.utils.escape_html(res.currency || "")}<br>
                            <strong>${__("Live Balance")}:</strong> ${bal}
                         </div>`
                    );
                },
            });
        },
    });
}

function rmax_load_bnpl_heads(frm, d, vals) {
    frappe.call({
        method: "rmax_custom.api.bnpl.get_clearing_account_for_mop",
        args: { mop: vals.mop, company: frm.doc.company },
        callback: function (r) {
            const res = r.message || {};
            if (!res.account) {
                frappe.msgprint({
                    title: __("Setup Missing"),
                    message: __(
                        "Configure a default account for {0} on Company {1} (Mode of Payment Account table).",
                        [vals.mop, frm.doc.company]
                    ),
                    indicator: "red",
                });
                return;
            }
            // Resolve the BNPL Fee Expense account by name convention.
            // Created by setup_bnpl_accounts at install / after_migrate.
            frappe.db
                .get_value(
                    "Account",
                    {
                        company: frm.doc.company,
                        account_name: ["like", "BNPL Fee Expense%"],
                        is_group: 0,
                    },
                    "name"
                )
                .then(function (rr) {
                    const fee = (rr.message || {}).name;
                    if (!fee) {
                        frappe.msgprint({
                            title: __("Setup Missing"),
                            message: __(
                                "No 'BNPL Fee Expense' account on Company {0}. Re-run setup_bnpl_accounts.",
                                [frm.doc.company]
                            ),
                            indicator: "red",
                        });
                        return;
                    }
                    frappe.confirm(
                        __("This replaces the existing accounts table. Continue?"),
                        function () {
                            frm.clear_table("accounts");
                            const r1 = frm.add_child("accounts");
                            r1.account = vals.bank_account;
                            r1.debit_in_account_currency = 0;
                            r1.credit_in_account_currency = 0;
                            const r2 = frm.add_child("accounts");
                            r2.account = fee;
                            r2.debit_in_account_currency = 0;
                            r2.credit_in_account_currency = 0;
                            const r3 = frm.add_child("accounts");
                            r3.account = res.account;
                            r3.debit_in_account_currency = 0;
                            r3.credit_in_account_currency = 0;
                            frm.refresh_field("accounts");
                            if (!frm.doc.user_remark) {
                                frm.set_value(
                                    "user_remark",
                                    __("BNPL Settlement — {0}", [vals.mop])
                                );
                            }
                            d.hide();
                        }
                    );
                });
        },
    });
}
