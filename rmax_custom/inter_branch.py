"""Inter-Branch Receivables & Payables — Phase 1 Foundation.

Single-company multi-branch GL: enables branch as a mandatory accounting
dimension enforced per-Company at the GL-posting layer, manages the
Inter-Branch chart-of-accounts groups + lazy leaves, auto-injects balancing
inter-branch legs into Journal Entries, and generates a companion inter-branch
JE for cross-branch Stock Transfers.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate


def _ensure_branch_accounting_dimension() -> None:
    """Enable Branch as an Accounting Dimension and mark it mandatory per Company.

    ERPNext enforces mandatory accounting dimensions at the GL-posting layer:
    when `mandatory_for_bs` and `mandatory_for_pl` are set on the per-Company
    row of `dimension_defaults`, every Balance-Sheet and P&L GL Entry for that
    company is rejected without a Branch value. This covers Journal Entry,
    Stock Entry, Payment Entry, and every other GL-posting doctype.

    Idempotent: safe to re-run from after_migrate.
    """
    dim_name = frappe.db.get_value("Accounting Dimension", {"document_type": "Branch"})
    if dim_name:
        dim = frappe.get_doc("Accounting Dimension", dim_name)
    else:
        dim = frappe.new_doc("Accounting Dimension")
        dim.document_type = "Branch"
        dim.disabled = 0
        dim.insert(ignore_permissions=True)

    if dim.disabled:
        dim.disabled = 0

    existing_companies = {row.company for row in (dim.dimension_defaults or [])}

    for company in frappe.get_all("Company", pluck="name"):
        if company in existing_companies:
            for row in dim.dimension_defaults:
                if row.company == company:
                    row.mandatory_for_bs = 1
                    row.mandatory_for_pl = 1
                    row.reference_document = "Branch"
        else:
            dim.append(
                "dimension_defaults",
                {
                    "company": company,
                    "reference_document": "Branch",
                    "mandatory_for_bs": 1,
                    "mandatory_for_pl": 1,
                },
            )

    dim.save(ignore_permissions=True)
    frappe.db.commit()


INTER_BRANCH_RECEIVABLE_LABEL = "Inter-Branch Receivable"
INTER_BRANCH_PAYABLE_LABEL = "Inter-Branch Payable"


def _company_abbr(company: str) -> str:
    return frappe.db.get_value("Company", company, "abbr")


def _find_parent_group(company: str, root_type: str, fallback_label: str) -> str:
    """Return the canonical parent group account name for a given root_type.

    Asset → "Current Assets - <abbr>" if it exists, else falls back to the
    company's root Asset group. Liability → "Current Liabilities - <abbr>".
    """
    abbr = _company_abbr(company)
    candidate = f"{fallback_label} - {abbr}"
    if frappe.db.exists("Account", candidate):
        return candidate

    # CoA variants prefix the account_name with a number (e.g. "1100-1600
    # - Current Assets - CL"). Match by account_name first.
    by_account_name = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "account_name": fallback_label,
            "is_group": 1,
            "root_type": root_type,
        },
        "name",
    )
    if by_account_name:
        return by_account_name

    # Fallback: the company root for the matching root_type. ERPNext
    # stores root accounts with parent_account = NULL, but some legacy
    # rows use "" — accept either.
    root = frappe.db.sql(
        """
        SELECT name FROM `tabAccount`
        WHERE company = %s
          AND root_type = %s
          AND is_group = 1
          AND (parent_account IS NULL OR parent_account = '')
        LIMIT 1
        """,
        (company, root_type),
    )
    if root:
        return root[0][0]
    frappe.throw(_("Cannot locate root {0} group for company {1}").format(root_type, company))


def _ensure_group_account(company: str, label: str, root_type: str, parent: str) -> str:
    abbr = _company_abbr(company)
    name = f"{label} - {abbr}"
    if frappe.db.exists("Account", name):
        return name

    acc = frappe.new_doc("Account")
    acc.account_name = label
    acc.company = company
    acc.parent_account = parent
    acc.is_group = 1
    acc.root_type = root_type
    if root_type == "Asset":
        acc.account_type = "Receivable"
    elif root_type == "Liability":
        acc.account_type = "Payable"
    acc.insert(ignore_permissions=True)
    return acc.name


def _ensure_inter_branch_groups(company: str) -> tuple[str, str]:
    """Create the two inter-branch parent groups under Current Assets / Current Liabilities."""
    rec_parent = _find_parent_group(company, "Asset", "Current Assets")
    pay_parent = _find_parent_group(company, "Liability", "Current Liabilities")

    receivable = _ensure_group_account(company, INTER_BRANCH_RECEIVABLE_LABEL, "Asset", rec_parent)
    payable = _ensure_group_account(company, INTER_BRANCH_PAYABLE_LABEL, "Liability", pay_parent)
    return receivable, payable


def _slug(text: str) -> str:
    """Strip non-alphanumeric chars to keep account name compact."""
    return "".join(ch for ch in text if ch.isalnum() or ch == " ").strip()


def get_or_create_inter_branch_account(
    company: str, counterparty_branch: str, side: str
) -> str:
    """Return the leaf account name for the given counterparty + side.

    side = "receivable" → "Due from <Branch> - <abbr>" under Inter-Branch Receivable group
    side = "payable"    → "Due to <Branch> - <abbr>" under Inter-Branch Payable group

    Creates the account on first call; subsequent calls return the existing name.
    """
    if side not in ("receivable", "payable"):
        raise ValueError(f"side must be 'receivable' or 'payable', got: {side!r}")

    abbr = _company_abbr(company)
    if side == "receivable":
        prefix = "Due from"
        parent = f"{INTER_BRANCH_RECEIVABLE_LABEL} - {abbr}"
        root_type = "Asset"
    else:
        prefix = "Due to"
        parent = f"{INTER_BRANCH_PAYABLE_LABEL} - {abbr}"
        root_type = "Liability"

    if not frappe.db.exists("Account", parent):
        _ensure_inter_branch_groups(company)

    leaf_label = f"{prefix} {_slug(counterparty_branch)}"
    leaf_name = f"{leaf_label} - {abbr}"

    if frappe.db.exists("Account", leaf_name):
        return leaf_name

    company_currency = frappe.db.get_value("Company", company, "default_currency")
    acc = frappe.new_doc("Account")
    acc.account_name = leaf_label
    acc.company = company
    acc.parent_account = parent
    acc.is_group = 0
    acc.root_type = root_type
    # Leaf account_type left blank so JE entries do not require a Party.
    acc.account_currency = company_currency
    acc.insert(ignore_permissions=True)
    return acc.name


def on_branch_insert(doc, method=None) -> None:
    """Branch.after_insert hook.

    For every Company in the system, create the receivable + payable leaves
    that connect the new branch to every other existing branch. Emits a
    msgprint warning so the operator knows accounts were auto-loaded.
    """
    new_branch = doc.name
    # Only create against root-level companies; ERPNext auto-syncs to children.
    companies = frappe.get_all(
        "Company",
        filters={"parent_company": ["in", ["", None]]},
        pluck="name",
    )

    created: list[str] = []
    for company in companies:
        _ensure_inter_branch_groups(company)
        existing_branches = [
            b for b in frappe.get_all("Branch", pluck="name") if b != new_branch
        ]
        for other in existing_branches:
            for side in ("receivable", "payable"):
                # Leaves on the new branch that reference each existing counterparty
                created.append(get_or_create_inter_branch_account(company, other, side))
                # And reverse: existing branches need leaves referencing the new branch
                created.append(get_or_create_inter_branch_account(company, new_branch, side))

    frappe.msgprint(
        _(
            "Inter-Branch account heads have been auto-loaded for branch <b>{0}</b>. "
            "Verify the Chart of Accounts before posting transactions."
        ).format(new_branch),
        title=_("Inter-Branch Accounts Created"),
        indicator="orange",
    )


def _per_branch_imbalance(je) -> dict[str, float]:
    """Return {branch: signed_imbalance}; positive = excess debit, negative = excess credit."""
    totals: dict[str, float] = {}
    for row in je.accounts or []:
        br = (row.branch or "").strip()
        if not br:
            continue
        totals[br] = totals.get(br, 0.0) + flt(row.debit_in_account_currency) - flt(
            row.credit_in_account_currency
        )
    return {br: round(v, 2) for br, v in totals.items() if abs(v) >= 0.01}


def _is_pre_cut_over(je) -> bool:
    cut_over = frappe.db.get_value(
        "Company", je.company, "custom_inter_branch_cut_over_date"
    )
    if not cut_over:
        # No cut-over configured = injector disabled for this company
        return True
    return getdate(je.posting_date) < getdate(cut_over)


def _strip_existing_auto_legs(je) -> None:
    """Remove any prior auto-injected rows so we can recompute idempotently."""
    je.accounts = [
        row for row in (je.accounts or []) if not getattr(row, "custom_auto_inserted", 0)
    ]


def _inject_pair(
    doc,
    debtor: str,
    creditor: str,
    amount: float,
    source_doctype: str,
    source_docname: str,
) -> None:
    """Append two balancing rows: debtor's payable + creditor's receivable.

    `amount` is always positive (in company currency, equal to account currency
    because all inter-branch leaves are in Company default currency).
    """
    debtor_payable = get_or_create_inter_branch_account(doc.company, creditor, side="payable")
    creditor_receivable = get_or_create_inter_branch_account(doc.company, debtor, side="receivable")

    company_currency = frappe.db.get_value("Company", doc.company, "default_currency")
    debtor_currency = frappe.db.get_value("Account", debtor_payable, "account_currency") or company_currency
    creditor_currency = frappe.db.get_value("Account", creditor_receivable, "account_currency") or company_currency

    doc.append(
        "accounts",
        {
            "account": debtor_payable,
            "account_currency": debtor_currency,
            "exchange_rate": 1,
            "credit_in_account_currency": amount,
            "credit": amount,
            "branch": debtor,
            "custom_auto_inserted": 1,
            "custom_source_doctype": source_doctype or "Journal Entry",
            "custom_source_docname": source_docname or doc.name or "",
            "user_remark": _("Auto-injected: {0} owes {1}").format(debtor, creditor),
        },
    )
    doc.append(
        "accounts",
        {
            "account": creditor_receivable,
            "account_currency": creditor_currency,
            "exchange_rate": 1,
            "debit_in_account_currency": amount,
            "debit": amount,
            "branch": creditor,
            "custom_auto_inserted": 1,
            "custom_source_doctype": source_doctype or "Journal Entry",
            "custom_source_docname": source_docname or doc.name or "",
            "user_remark": _("Auto-injected: {0} receivable from {1}").format(creditor, debtor),
        },
    )


def auto_inject_inter_branch_legs(doc, method=None) -> None:
    """Journal Entry.validate hook.

    If the JE touches multiple branches and per-branch debits ≠ credits,
    inject `Inter-Branch — <other>` balancing legs so each branch zeroes.

    For 2-branch JEs the counterparty is unambiguous and inferred from the
    imbalance. For 3+-branch JEs the Company's `custom_inter_branch_bridge_branch`
    field designates the implicit bridge — every other branch is paired against
    it. The bridge must appear in the JE.
    """
    if doc.doctype != "Journal Entry":
        return
    if doc.flags.get("skip_inter_branch_injection"):
        return
    if not doc.company:
        return
    if _is_pre_cut_over(doc):
        return

    _strip_existing_auto_legs(doc)
    imbalance = _per_branch_imbalance(doc)

    if not imbalance:
        return

    if len(imbalance) < 2:
        # Single branch is unbalanced → standard JE validation will catch it
        return

    # Sanity: the JE must be globally balanced before injection (sum of deltas == 0)
    if round(sum(imbalance.values()), 2) != 0:
        frappe.throw(
            _(
                "Journal Entry totals are unbalanced before inter-branch injection. "
                "Per-branch deltas: {0}"
            ).format(imbalance),
            title=_("Unbalanced Journal Entry"),
        )

    # Source traceability — reuse any pre-stamped source on the JE
    source_doctype = ""
    source_docname = ""
    for row in doc.accounts:
        if getattr(row, "custom_source_doctype", None):
            source_doctype = row.custom_source_doctype
            source_docname = row.custom_source_docname or ""
            break

    if len(imbalance) == 2:
        # Direct 2-branch case — counterparty is the other branch in the pair
        branch_a, branch_b = sorted(imbalance.keys())
        delta_a = imbalance[branch_a]
        delta_b = imbalance[branch_b]
        if delta_a > delta_b:
            debtor, creditor, amount = branch_a, branch_b, delta_a
        else:
            debtor, creditor, amount = branch_b, branch_a, delta_b
        _inject_pair(doc, debtor, creditor, amount, source_doctype, source_docname)
    else:
        # 3+ branches — require a bridge branch configured on Company
        bridge = frappe.db.get_value(
            "Company", doc.company, "custom_inter_branch_bridge_branch"
        )
        if not bridge:
            frappe.throw(
                _(
                    "This Journal Entry touches {0} branches: <b>{1}</b>. "
                    "Multi-branch entries require the Company's "
                    "<b>Inter-Branch Bridge Branch</b> setting (Company → Inter-Branch Bridge Branch). "
                    "Either configure the bridge or split into separate two-branch Journal Entries."
                ).format(len(imbalance), ", ".join(sorted(imbalance))),
                title=_("Bridge Branch Not Configured"),
            )
        if bridge not in imbalance:
            frappe.throw(
                _(
                    "This Journal Entry touches branches <b>{0}</b>, but the "
                    "configured bridge branch <b>{1}</b> is not among them. "
                    "Add at least one line on branch <b>{1}</b>, or split into "
                    "separate two-branch Journal Entries."
                ).format(", ".join(sorted(imbalance)), bridge),
                title=_("Bridge Branch Missing From Journal Entry"),
            )

        # For each non-bridge branch, pair it against the bridge.
        for other_branch, delta in sorted(imbalance.items()):
            if other_branch == bridge:
                continue
            if delta > 0:
                # other_branch consumed value paid by bridge → other owes bridge
                debtor, creditor, amount = other_branch, bridge, delta
            else:
                # other_branch paid value consumed by bridge → bridge owes other
                debtor, creditor, amount = bridge, other_branch, abs(delta)
            _inject_pair(doc, debtor, creditor, amount, source_doctype, source_docname)

    # Final guard — every branch must now balance to zero
    final = _per_branch_imbalance(doc)
    if final:
        frappe.throw(
            _("Auto-injection failed to balance branches: {0}").format(final),
            title=_("Inter-Branch Auto-Injection Error"),
        )


def resolve_warehouse_branch(warehouse: str) -> str | None:
    """Look up the Branch linked to a warehouse via Branch Configuration.

    Returns None when no mapping exists. The first matching mapping wins
    (multiple Branch Configurations could reference the same warehouse —
    in RMAX this is rare and indicates shared-warehouse setups).
    """
    if not warehouse:
        return None
    rows = frappe.db.sql(
        """
        SELECT bc.branch
        FROM `tabBranch Configuration Warehouse` bcw
        INNER JOIN `tabBranch Configuration` bc ON bc.name = bcw.parent
        WHERE bcw.warehouse = %s AND bc.branch IS NOT NULL
        ORDER BY bc.modified DESC
        LIMIT 1
        """,
        (warehouse,),
    )
    return rows[0][0] if rows else None


@frappe.whitelist()
def backfill_je_header_source() -> int:
    """Populate `custom_source_doctype` and `custom_source_docname` on the Journal
    Entry header for any submitted JE whose child accounts already carry those
    fields but whose header was created before the Phase 2 dashboard support.

    Returns the count of JEs updated. Idempotent — only touches rows where the
    header field is empty AND the child rows agree on a single source.

    Run: `bench --site rmax_dev2 execute rmax_custom.inter_branch.backfill_je_header_source`
    """
    rows = frappe.db.sql(
        """
        SELECT je.name, MIN(jea.custom_source_doctype) AS dt, MIN(jea.custom_source_docname) AS dn,
               COUNT(DISTINCT jea.custom_source_docname) AS distinct_dns
        FROM `tabJournal Entry` je
        INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
        WHERE jea.custom_auto_inserted = 1
          AND jea.custom_source_doctype IS NOT NULL
          AND jea.custom_source_doctype != ''
          AND jea.custom_source_docname IS NOT NULL
          AND jea.custom_source_docname != ''
          AND (je.custom_source_docname IS NULL OR je.custom_source_docname = '')
          AND je.docstatus = 1
        GROUP BY je.name
        HAVING distinct_dns = 1
        """,
        as_dict=True,
    )
    updated = 0
    for r in rows:
        frappe.db.set_value(
            "Journal Entry",
            r.name,
            {"custom_source_doctype": r.dt, "custom_source_docname": r.dn},
            update_modified=False,
        )
        updated += 1
    frappe.db.commit()
    print(f"Backfilled {updated} Journal Entry header(s).")
    return updated


@frappe.whitelist()
def print_reconciliation(company: str, from_date: str = "2026-01-01", to_date: str = "2026-12-31") -> None:
    """Print the Inter-Branch Reconciliation matrix to stdout (debug helper)."""
    from rmax_custom.rmax_custom.report.inter_branch_reconciliation.inter_branch_reconciliation import execute as run_report
    columns, data = run_report({"company": company, "from_date": from_date, "to_date": to_date})

    label_map = {c["fieldname"]: c["label"] for c in columns}

    def col_has_data(fn, rows):
        return any(abs(flt(r.get(fn, 0))) > 0.01 for r in rows)

    active_fields = [c["fieldname"] for c in columns[1:] if col_has_data(c["fieldname"], data)]

    def row_has_data(r):
        return any(abs(flt(r.get(f, 0))) > 0.01 for f in active_fields)

    active_rows = [r for r in data if row_has_data(r)]

    print("=== INTER-BRANCH RECONCILIATION ===")
    print(f"Company: {company}    Period: {from_date} to {to_date}")
    print("")
    if not active_rows:
        print("(No inter-branch activity in the period.)")
        return
    header = ["From \\ To"] + [label_map[f] for f in active_fields]
    print("  " + " | ".join(f"{h:18s}" for h in header))
    print("  " + "-" * (21 * len(header)))
    for r in active_rows:
        cells = [r.get("from_branch", "")]
        for f in active_fields:
            cells.append(f"{flt(r.get(f, 0)):.2f}")
        print("  " + " | ".join(f"{c:18s}" for c in cells))
    print("")
    print("=== HEALTH CHECK (each pair must net to zero) ===")
    seen = set()
    for r in active_rows:
        fb = r.get("from_branch")
        for f in active_fields:
            tb = label_map[f]
            if fb == tb:
                continue
            ab = flt(r.get(f, 0))
            if abs(ab) < 0.01:
                continue
            pair = tuple(sorted([fb, tb]))
            if pair in seen:
                continue
            seen.add(pair)
            ba = 0.0
            rev_field = next((f2 for f2 in active_fields if label_map[f2] == fb), None)
            for r2 in active_rows:
                if r2.get("from_branch") == tb and rev_field:
                    ba = flt(r2.get(rev_field, 0))
                    break
            net = ab + ba
            status = "OK" if abs(net) < 0.01 else "MISMATCH"
            print(f"  {fb:8s} -> {tb:8s} = {ab:8.2f}    {tb:8s} -> {fb:8s} = {ba:8.2f}    sum = {net:8.2f}  [{status}]")


def setup_inter_branch_foundation() -> None:
    """Idempotent entrypoint called from setup.after_migrate.

    Only root-level companies (no parent_company) get the Inter-Branch groups
    created directly. ERPNext auto-syncs accounts from a root company down to
    its child companies via `validate_root_company_and_sync_account_to_children`.
    """
    _ensure_branch_accounting_dimension()
    root_companies = frappe.get_all(
        "Company",
        filters={"parent_company": ["in", ["", None]]},
        pluck="name",
    )
    for company_name in root_companies:
        _ensure_inter_branch_groups(company_name)


def _stock_transfer_total_value(stock_transfer) -> float:
    """Sum item value (qty x source-warehouse valuation rate) across the
    Stock Transfer items table.

    The custom Stock Transfer Item DocType deliberately does NOT carry
    basic_amount / basic_rate / valuation_rate columns (it's a request
    document, not a stock-posting document). The valuation that the
    underlying Stock Entry will book is read live from each item's Bin
    row at the source warehouse. Falls back to Item.valuation_rate when
    the Bin row doesn't exist yet.
    """
    source_wh = getattr(stock_transfer, "set_source_warehouse", None)
    if not source_wh:
        return 0.0

    total = 0.0
    for item in stock_transfer.items or []:
        qty = flt(getattr(item, "quantity", 0)) or flt(getattr(item, "qty", 0))
        if qty <= 0 or not getattr(item, "item_code", None):
            continue
        rate = flt(
            frappe.db.get_value(
                "Bin",
                {"item_code": item.item_code, "warehouse": source_wh},
                "valuation_rate",
            )
        )
        if not rate:
            rate = flt(frappe.db.get_value("Item", item.item_code, "valuation_rate"))
        total += qty * rate
    return round(total, 2)


def create_companion_inter_branch_je_for_stock_transfer(stock_transfer) -> str | None:
    """Create a 2-line Journal Entry that records the inter-branch obligation
    arising from a cross-branch Stock Transfer at valuation cost.

    Returns the new JE name, or None if no JE was needed (same-branch transfer).

    Posts:
        Dr Inter-Branch—<target>  (branch = <source>)  — source has receivable from target
        Cr Inter-Branch—<source>  (branch = <target>)  — target owes source

    The JE is balanced as a unit (debit total = credit total). Mark
    `flags.skip_inter_branch_injection = True` so the auto-injector does not
    attempt to add additional legs (per-branch the JE is intentionally one-sided
    because the underlying Stock Entry's GL contributes the offsetting Stock-in-Hand
    legs to each branch).
    """
    source_wh = getattr(stock_transfer, "set_source_warehouse", None)
    target_wh = getattr(stock_transfer, "set_target_warehouse", None)
    source_branch = resolve_warehouse_branch(source_wh)
    target_branch = resolve_warehouse_branch(target_wh)

    if not source_branch or not target_branch:
        return None
    if source_branch == target_branch:
        return None
    if _is_pre_cut_over(stock_transfer):
        return None

    amount = _stock_transfer_total_value(stock_transfer)
    if amount <= 0:
        return None

    company = stock_transfer.company

    src_receivable = get_or_create_inter_branch_account(company, target_branch, "receivable")
    tgt_payable = get_or_create_inter_branch_account(company, source_branch, "payable")

    company_currency = frappe.db.get_value("Company", company, "default_currency")
    src_currency = frappe.db.get_value("Account", src_receivable, "account_currency") or company_currency
    tgt_currency = frappe.db.get_value("Account", tgt_payable, "account_currency") or company_currency

    je = frappe.new_doc("Journal Entry")
    je.posting_date = stock_transfer.posting_date
    je.company = company
    je.voucher_type = "Journal Entry"
    je.custom_source_doctype = "Stock Transfer"
    je.custom_source_docname = stock_transfer.name
    je.user_remark = _("Inter-Branch obligation from Stock Transfer {0}").format(
        stock_transfer.name
    )
    je.append(
        "accounts",
        {
            "account": src_receivable,
            "account_currency": src_currency,
            "exchange_rate": 1,
            "debit_in_account_currency": amount,
            "debit": amount,
            "branch": source_branch,
            "custom_auto_inserted": 1,
            "custom_source_doctype": "Stock Transfer",
            "custom_source_docname": stock_transfer.name,
        },
    )
    je.append(
        "accounts",
        {
            "account": tgt_payable,
            "account_currency": tgt_currency,
            "exchange_rate": 1,
            "credit_in_account_currency": amount,
            "credit": amount,
            "branch": target_branch,
            "custom_auto_inserted": 1,
            "custom_source_doctype": "Stock Transfer",
            "custom_source_docname": stock_transfer.name,
        },
    )
    je.flags.skip_inter_branch_injection = True
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


# ----------------------------------------------------------------------------
# Direct Stock Entry hooks (no Stock Transfer wrapper)
# ----------------------------------------------------------------------------

# Stock Entry purposes that move inventory between two warehouses on a single SE.
# Phase 1 only handles the simple Material Transfer flow.
STOCK_ENTRY_INTER_BRANCH_PURPOSES = ("Material Transfer",)


def _stock_entry_branch_pair(stock_entry) -> tuple[str | None, str | None, float]:
    """Return (source_branch, target_branch, total_value) for a Material Transfer SE.

    Walks every item row, resolves each row's `s_warehouse` and `t_warehouse`
    to a Branch via Branch Configuration, and:

    * if every row carries the same (source_branch, target_branch) pair,
      returns that pair plus the summed valuation; rows whose warehouses do
      not map to a Branch are tolerated only if their pair matches the
      dominant pair.
    * if rows disagree on the pair (multi-pair SE — out of scope for Phase 1),
      returns (None, None, 0.0) so the caller skips with a warning.

    `total_value` sums `basic_amount`, falling back to `qty * basic_rate`
    when ERPNext has not stamped basic_amount yet.
    """
    pairs: dict[tuple[str, str], float] = {}
    for item in stock_entry.items or []:
        s_wh = getattr(item, "s_warehouse", None)
        t_wh = getattr(item, "t_warehouse", None)
        if not s_wh or not t_wh:
            continue
        s_br = resolve_warehouse_branch(s_wh)
        t_br = resolve_warehouse_branch(t_wh)
        if not s_br or not t_br:
            continue
        amt = flt(getattr(item, "basic_amount", 0))
        if not amt:
            amt = flt(getattr(item, "qty", 0)) * flt(getattr(item, "basic_rate", 0))
        pairs[(s_br, t_br)] = pairs.get((s_br, t_br), 0.0) + amt

    if not pairs:
        return None, None, 0.0
    if len(pairs) > 1:
        # Multi-pair SE — Phase 1 does not handle this; log a hint to ops.
        frappe.log_error(
            title="Inter-Branch SE skipped (multi-pair)",
            message=(
                f"Stock Entry {stock_entry.name} moves stock across multiple "
                f"branch pairs: {sorted(pairs)}. Phase 1 supports only single-pair "
                f"Material Transfer SEs. Split this SE into one-pair-per-doc."
            ),
        )
        return None, None, 0.0

    (src, tgt), total = next(iter(pairs.items()))
    return src, tgt, round(total, 2)


def _retag_se_gl_entries(stock_entry, source_branch: str, target_branch: str) -> None:
    """Rewrite per-leg branch tags on a freshly-submitted Stock Entry's GL.

    ERPNext's `make_gl_entries` copies the SE header `branch` (or the row's
    `branch` field) onto every GL row. For cross-branch transfers we need:

      * source warehouse legs (Cr Stock-in-Hand on source) → branch=<source>
      * target warehouse legs (Dr Stock-in-Hand on target) → branch=<target>

    Resolved by the warehouse linked to each GL row.
    """
    gl_rows = frappe.get_all(
        "GL Entry",
        filters={"voucher_no": stock_entry.name, "is_cancelled": 0},
        fields=["name", "account", "debit", "credit"],
    )
    for row in gl_rows:
        warehouse = frappe.db.get_value("Account", row.account, "warehouse")
        if not warehouse:
            continue
        wh_branch = resolve_warehouse_branch(warehouse)
        if not wh_branch:
            continue
        if wh_branch not in (source_branch, target_branch):
            continue
        frappe.db.set_value("GL Entry", row.name, "branch", wh_branch, update_modified=False)


def create_companion_inter_branch_je_for_stock_entry(
    stock_entry, source_branch: str, target_branch: str, amount: float
) -> str | None:
    """Mirror of the Stock Transfer companion JE, sourced from a direct SE.

    Posts:
        Dr Inter-Branch—<target>  (branch=<source>)
        Cr Inter-Branch—<source>  (branch=<target>)
    """
    if amount <= 0:
        return None
    if source_branch == target_branch:
        return None
    if _is_pre_cut_over(stock_entry):
        return None

    company = stock_entry.company
    src_receivable = get_or_create_inter_branch_account(company, target_branch, "receivable")
    tgt_payable = get_or_create_inter_branch_account(company, source_branch, "payable")

    company_currency = frappe.db.get_value("Company", company, "default_currency")
    src_currency = frappe.db.get_value("Account", src_receivable, "account_currency") or company_currency
    tgt_currency = frappe.db.get_value("Account", tgt_payable, "account_currency") or company_currency

    je = frappe.new_doc("Journal Entry")
    je.posting_date = stock_entry.posting_date
    je.company = company
    je.voucher_type = "Journal Entry"
    je.custom_source_doctype = "Stock Entry"
    je.custom_source_docname = stock_entry.name
    je.user_remark = _("Inter-Branch obligation from Stock Entry {0}").format(
        stock_entry.name
    )
    je.append(
        "accounts",
        {
            "account": src_receivable,
            "account_currency": src_currency,
            "exchange_rate": 1,
            "debit_in_account_currency": amount,
            "debit": amount,
            "branch": source_branch,
            "custom_auto_inserted": 1,
            "custom_source_doctype": "Stock Entry",
            "custom_source_docname": stock_entry.name,
        },
    )
    je.append(
        "accounts",
        {
            "account": tgt_payable,
            "account_currency": tgt_currency,
            "exchange_rate": 1,
            "credit_in_account_currency": amount,
            "credit": amount,
            "branch": target_branch,
            "custom_auto_inserted": 1,
            "custom_source_doctype": "Stock Entry",
            "custom_source_docname": stock_entry.name,
        },
    )
    je.flags.skip_inter_branch_injection = True
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


def auto_set_branch_from_warehouse(doc, method=None) -> None:
    """Populate `branch` from each item row's warehouse mapping.

    Hook target: any submittable stock-side doctype whose items carry a
    `warehouse` field (or `s_warehouse` / `t_warehouse` for Stock Entry).
    Avoids the per-Company `mandatory_for_bs` GL rejection on Stock
    Reconciliation, opening stock, Stock Entry repacks, etc.

    Behaviour:
      * Per item row, resolve the warehouse → branch via Branch
        Configuration. If a mapping exists, OVERRIDE the row's branch
        with the resolved value — warehouse is authoritative on stock
        documents. Operators selecting a mismatched branch (e.g. SR row
        on Azzizziyah-CL warehouse but branch=Warehouse Jeddah) get
        their pick replaced silently to keep GL entries consistent.
      * Header `branch` is set to the first item's resolved branch when
        items agree. When the item rows resolve to multiple branches,
        the header is left as set (the per-row branch carries the
        accounting dimension on each GL Entry anyway).
      * Rows whose warehouse is not mapped (or has no warehouse) are
        left untouched.
      * Roles bypass: System Manager and Stock Manager are trusted to
        manually override — no auto-correction for them.

    Material Transfer Stock Entry rows have BOTH `s_warehouse` and
    `t_warehouse`; this helper fills `branch` from the source side
    because that's the warehouse the GL row will hang on for the credit
    leg. The target-side leg's branch is corrected post-submit by
    `_retag_se_gl_entries`.
    """
    items = getattr(doc, "items", None)
    if not items:
        return

    user = frappe.session.user
    if user == "Administrator":
        return
    roles = set(frappe.get_roles(user))
    if roles & {"System Manager", "Stock Manager"}:
        return

    resolved_branches = set()
    first_resolved = None
    overridden = False
    for item in items:
        wh = (
            getattr(item, "warehouse", None)
            or getattr(item, "s_warehouse", None)
            or getattr(item, "t_warehouse", None)
        )
        if not wh:
            continue
        br = resolve_warehouse_branch(wh)
        if not br:
            continue
        # OVERRIDE — warehouse is the source of truth for stock GL.
        prior = getattr(item, "branch", None)
        if prior and prior != br:
            overridden = True
        item.branch = br
        resolved_branches.add(br)
        if first_resolved is None:
            first_resolved = br

    # Header branch is consistent only when every resolved item agrees.
    if first_resolved and len(resolved_branches) == 1:
        prior_header = getattr(doc, "branch", None)
        if prior_header and prior_header != first_resolved:
            overridden = True
        doc.branch = first_resolved

    if overridden and not doc.flags.get("rmax_branch_auto_corrected_msg"):
        doc.flags.rmax_branch_auto_corrected_msg = True
        frappe.msgprint(
            _(
                "Branch auto-corrected from the warehouse mapping to keep GL "
                "entries consistent. Pick the correct warehouse if you intended "
                "a different branch."
            ),
            indicator="orange",
            title=_("Branch Adjusted"),
            alert=True,
        )


def on_stock_entry_submit(doc, method=None) -> None:
    """Stock Entry.on_submit hook.

    Generates an inter-branch companion JE and re-tags per-leg GL Entry
    branches when source and target warehouses sit on different branches.

    Skipped when:
      * SE was created by a Stock Transfer (the ST hook handles it)
      * SE purpose is not in STOCK_ENTRY_INTER_BRANCH_PURPOSES
      * SE warehouses map to the same branch (intra-branch shuffle)
      * Company cut-over date is not yet reached
      * A companion JE already exists for this SE name (idempotency)
    """
    if doc.doctype != "Stock Entry":
        return
    if doc.flags.get("from_stock_transfer"):
        return
    if doc.purpose not in STOCK_ENTRY_INTER_BRANCH_PURPOSES:
        return
    if not doc.company:
        return

    # Idempotency — if a JE sourced from this SE already exists, do nothing
    existing = frappe.db.exists(
        "Journal Entry Account",
        {
            "custom_source_doctype": "Stock Entry",
            "custom_source_docname": doc.name,
            "docstatus": 1,
        },
    )
    if existing:
        return

    source_branch, target_branch, amount = _stock_entry_branch_pair(doc)
    if not source_branch or not target_branch:
        return
    if source_branch == target_branch:
        return

    _retag_se_gl_entries(doc, source_branch, target_branch)
    create_companion_inter_branch_je_for_stock_entry(
        doc, source_branch, target_branch, amount
    )


def on_stock_entry_cancel(doc, method=None) -> None:
    """Stock Entry.on_cancel hook — cancel the linked companion JE if present."""
    if doc.doctype != "Stock Entry":
        return
    try:
        companion_names = frappe.db.sql_list(
            """
            SELECT DISTINCT je.name
            FROM `tabJournal Entry` je
            INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
            WHERE jea.custom_source_doctype = 'Stock Entry'
              AND jea.custom_source_docname = %s
              AND je.docstatus = 1
            """,
            (doc.name,),
        )
        for je_name in companion_names:
            je_doc = frappe.get_doc("Journal Entry", je_name)
            je_doc.flags.skip_inter_branch_injection = True
            je_doc.cancel()
    except Exception:
        frappe.log_error(
            title="Inter-Branch SE companion JE cancel failed",
            message=frappe.get_traceback(),
        )
        raise
