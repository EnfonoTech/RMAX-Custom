/**
 * RMAX Custom: Delivery Note form — Inter-Company mode.
 *
 * Ticking `Inter Company` restricts the customer dropdown to internal
 * customers and locks the selling price list to "Inter Company Price".
 */

const RMAX_INTER_COMPANY_PRICE_LIST = "Inter Company Price";

frappe.ui.form.on("Delivery Note", {
    onload: function (frm) {
        _rmax_apply_inter_company_mode(frm);
    },
    refresh: function (frm) {
        _rmax_apply_inter_company_mode(frm);
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
        }
    },
});

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
}
