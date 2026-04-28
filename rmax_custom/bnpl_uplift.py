"""
BNPL Surcharge Uplift for Sales Invoice.

Implements the Tabby/Tamara uplift mechanism per BRD "Tabby RMAX" v1:

    new_rate = original_rate * (1 + bnpl_portion_ratio * surcharge_pct / 100)

For each Sales Invoice Item, the pre-uplift selling rate is preserved on
custom_original_rate. The uplift only fires when the Payments table
contains rows whose Mode of Payment carries a non-zero
custom_surcharge_percentage. COGS, Stock Ledger, and item valuation are
not touched — only the selling-side rate field.

The same logic runs on the client (sales_invoice_doctype.js) for live
recalculation in the form, and here on before_validate as the source of
truth for REST API / Data Import / programmatic invoice creation.

A separate validate hook re-checks the maths after ERPNext's own
calculations and blocks submission on drift.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt


SURCHARGE_FIELD = "custom_surcharge_percentage"
ROUNDING_TOLERANCE = 0.01  # SAR


def _surcharge_cache(doc):
    """Cache surcharge % per Mode of Payment for the lifetime of one save."""
    cache = getattr(doc, "_bnpl_surcharge_cache", None)
    if cache is None:
        cache = {}
        doc._bnpl_surcharge_cache = cache
    return cache


def _get_surcharge_pct(doc, mode_of_payment):
    if not mode_of_payment:
        return 0.0
    cache = _surcharge_cache(doc)
    if mode_of_payment in cache:
        return cache[mode_of_payment]
    pct = flt(
        frappe.db.get_value("Mode of Payment", mode_of_payment, SURCHARGE_FIELD)
    )
    cache[mode_of_payment] = pct
    return pct


def _read_payment_breakdown(doc):
    """Resolve the list of (mode_of_payment, amount) pairs for ratio calc.

    Three sources, in priority order:

    1. ``custom_pos_payments_json`` on the in-memory doc — populated by
       the RMAX POS popup before ``frm.save()`` and forwarded with the
       save POST. Frappe's form serialiser sometimes drops hidden field
       writes for already-saved docs, so this isn't always reliable on
       its own.

    2. ``custom_pos_payments_json`` re-read from the DB. The popup also
       persists the snapshot via the
       ``rmax_custom.api.bnpl.set_pos_payments_snapshot`` whitelisted
       method *before* it triggers ``frm.save()``. That guarantees the
       value is in the DB even when (1) gets dropped from the POST.

    3. ``doc.payments`` — the standard ERPNext POS payments child table.
       Populated when ``is_pos = 1`` is set on the Sales Invoice.

    Returning an empty list means "no BNPL info available" — uplift skips.
    """
    raw = doc.get("custom_pos_payments_json")

    if not raw and doc.get("name") and not str(doc.get("name")).startswith("new-"):
        try:
            raw = frappe.db.get_value(
                "Sales Invoice", doc.name, "custom_pos_payments_json"
            )
        except Exception:
            raw = None
        if raw:
            doc.custom_pos_payments_json = raw

    if raw:
        try:
            rows = json.loads(raw)
        except (TypeError, ValueError):
            rows = []
        if isinstance(rows, list) and rows:
            return [
                (r.get("mode_of_payment"), flt(r.get("amount")))
                for r in rows
                if isinstance(r, dict) and r.get("mode_of_payment")
            ]

    return [
        (p.mode_of_payment, flt(p.amount))
        for p in (doc.get("payments") or [])
        if p.mode_of_payment
    ]


def _compute_factor(doc):
    """Return (bnpl_portion_ratio, weighted_uplift_factor).

    bnpl_portion_ratio: fraction of payments using a BNPL Mode of Payment
        (one with a non-zero surcharge %). 0 — 1.

    weighted_uplift_factor: 1 + (sum(amount_i * surcharge_pct_i) / total).
        Equals 1.0 when there are no BNPL payments. Supports a mix of BNPL
        providers with different surcharge rates by weighted average.
    """
    rows = _read_payment_breakdown(doc)
    total = sum(amt for _, amt in rows)
    if total <= 0:
        return 0.0, 1.0

    bnpl_amount = 0.0
    weighted_pct_sum = 0.0
    for mode, amt in rows:
        pct = _get_surcharge_pct(doc, mode)
        if pct > 0:
            bnpl_amount += amt
            weighted_pct_sum += amt * pct

    ratio = bnpl_amount / total if total else 0.0
    factor = 1 + (weighted_pct_sum / total) / 100.0
    return ratio, factor


def apply_bnpl_uplift(doc, method=None):
    """before_validate hook: stamp custom_original_rate and apply uplift.

    Idempotent — safe to re-run on the same document. When the BNPL ratio
    drops to zero the rates are restored from custom_original_rate and the
    uplift fields are cleared, so switching the Mode of Payment from Tabby
    to Cash undoes the uplift cleanly.
    """
    if doc.doctype != "Sales Invoice":
        return

    items = doc.get("items") or []
    if not items:
        return

    ratio, factor = _compute_factor(doc)

    if ratio <= 0:
        for row in items:
            original = flt(row.get("custom_original_rate"))
            if original > 0:
                row.rate = original
            row.custom_original_rate = 0
            row.custom_bnpl_uplift_amount = 0
        doc.custom_bnpl_portion_ratio = 0
        doc.custom_bnpl_total_uplift = 0
        return

    total_uplift = 0.0
    for row in items:
        base = flt(row.get("custom_original_rate")) or flt(row.rate)
        if base <= 0:
            row.custom_original_rate = 0
            row.custom_bnpl_uplift_amount = 0
            continue
        new_rate = flt(base * factor, row.precision("rate"))
        row.custom_original_rate = base
        row.rate = new_rate
        line_uplift = flt(
            (new_rate - base) * flt(row.qty), row.precision("amount")
        )
        row.custom_bnpl_uplift_amount = line_uplift
        total_uplift += line_uplift

    doc.custom_bnpl_portion_ratio = flt(ratio * 100, 4)
    doc.custom_bnpl_total_uplift = flt(total_uplift, 2)


def validate_bnpl_uplift(doc, method=None):
    """validate hook: re-verify per BRD §5.3.

    Guards against REST/import paths that skip before_validate or pass
    pre-computed rates that don't match the configured surcharge.
    """
    if doc.doctype != "Sales Invoice":
        return

    items = doc.get("items") or []
    if not items:
        return

    ratio, factor = _compute_factor(doc)

    if ratio <= 0:
        for row in items:
            if flt(row.get("custom_bnpl_uplift_amount")) != 0:
                frappe.throw(
                    _(
                        "Row {0}: BNPL uplift recorded but no BNPL Mode of Payment present. "
                        "Clear the uplift fields or add the corresponding payment row."
                    ).format(row.idx),
                    title=_("BNPL Uplift Mismatch"),
                )
        return

    for row in items:
        base = flt(row.get("custom_original_rate"))
        if base <= 0:
            frappe.throw(
                _(
                    "Row {0}: BNPL payment is recorded but Original Rate is empty. "
                    "Re-enter the item rate so the system can capture the pre-uplift price."
                ).format(row.idx),
                title=_("BNPL Uplift Missing Original Rate"),
            )
        expected = flt(base * factor, row.precision("rate"))
        if abs(flt(row.rate) - expected) > ROUNDING_TOLERANCE:
            frappe.throw(
                _(
                    "Row {0}: rate {1} does not match the BNPL-uplifted rate {2} "
                    "computed from Original Rate {3} and surcharge factor {4}."
                ).format(
                    row.idx,
                    row.rate,
                    expected,
                    base,
                    flt(factor, 6),
                ),
                title=_("BNPL Uplift Mismatch"),
            )
