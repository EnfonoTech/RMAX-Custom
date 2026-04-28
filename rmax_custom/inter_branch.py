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

    # Fallback: the company root for the matching root_type
    root = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": root_type, "is_group": 1, "parent_account": ""},
        "name",
    )
    if not root:
        frappe.throw(_("Cannot locate root {0} group for company {1}").format(root_type, company))
    return root


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


def auto_inject_inter_branch_legs(doc, method=None) -> None:
    """Journal Entry.validate hook.

    If the JE touches multiple branches and per-branch debits ≠ credits,
    inject `Inter-Branch — <other>` balancing legs so each branch zeroes.
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

    if len(imbalance) > 2:
        frappe.throw(
            _(
                "Inter-Branch auto-injection supports exactly two branches per Journal Entry, "
                "but this entry touches: <b>{0}</b>. "
                "Please split into separate Journal Entries — one per branch pair."
            ).format(", ".join(sorted(imbalance))),
            title=_("Multi-Branch Journal Entry Not Supported"),
        )

    if len(imbalance) < 2:
        # Single branch is unbalanced → standard JE validation will catch it
        return

    branch_a, branch_b = sorted(imbalance.keys())
    delta_a = imbalance[branch_a]
    delta_b = imbalance[branch_b]

    if round(delta_a + delta_b, 2) != 0:
        frappe.throw(
            _(
                "Journal Entry totals are unbalanced before inter-branch injection: "
                "Branch {0} delta = {1}, Branch {2} delta = {3}."
            ).format(branch_a, delta_a, branch_b, delta_b),
            title=_("Unbalanced Journal Entry"),
        )

    # branch_a's excess debit (delta_a > delta_b) means branch_a has received value owed by branch_b.
    if delta_a > delta_b:
        debtor, creditor = branch_a, branch_b
        amount = delta_a
    else:
        debtor, creditor = branch_b, branch_a
        amount = delta_b

    debtor_payable = get_or_create_inter_branch_account(doc.company, creditor, side="payable")
    creditor_receivable = get_or_create_inter_branch_account(doc.company, debtor, side="receivable")

    company_currency = frappe.db.get_value("Company", doc.company, "default_currency")
    debtor_currency = frappe.db.get_value("Account", debtor_payable, "account_currency") or company_currency
    creditor_currency = frappe.db.get_value("Account", creditor_receivable, "account_currency") or company_currency

    source_doctype = ""
    source_docname = ""
    for row in doc.accounts:
        if getattr(row, "custom_source_doctype", None):
            source_doctype = row.custom_source_doctype
            source_docname = row.custom_source_docname or ""
            break

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
    """Sum the basic_amount across items; falls back to qty * basic_rate when needed."""
    total = 0.0
    for item in stock_transfer.items or []:
        amt = flt(getattr(item, "basic_amount", 0))
        if not amt:
            amt = flt(getattr(item, "qty", 0)) * flt(getattr(item, "basic_rate", 0))
        total += amt
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
