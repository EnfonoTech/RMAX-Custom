"""
Override cost center on document tax rows and items with the user's
default cost center from Branch Configuration.

This prevents "Not Permitted" errors when the tax template has a cost center
(e.g. "Main - CNC") that the branch user doesn't have access to.

Also sets the cost_center on the document header and items if not already set.

Also resolves the user's default Cash / Bank account per branch and rewrites
Sales Invoice payment rows accordingly. BNPL Modes of Payment (type=General)
are intentionally untouched.
"""

import frappe
from frappe import _
from frappe.utils import cint


def override_cost_center_from_branch(doc, method=None):
    """Before validate: replace cost center with user's default if they don't have access."""
    if frappe.session.user == "Administrator":
        return

    user_cost_center = _get_user_default_cost_center()
    if not user_cost_center:
        return

    # Check if user has permission for the current cost center
    # If not, override with their default
    company = doc.company

    # Override document-level cost center
    if doc.get("cost_center"):
        if not _user_has_cost_center_access(doc.cost_center):
            doc.cost_center = user_cost_center
    else:
        doc.cost_center = user_cost_center

    # Override item-level cost centers
    for item in doc.get("items") or []:
        if hasattr(item, "cost_center"):
            if item.cost_center and not _user_has_cost_center_access(item.cost_center):
                item.cost_center = user_cost_center
            elif not item.cost_center:
                item.cost_center = user_cost_center

    # Override tax-level cost centers
    for tax in doc.get("taxes") or []:
        if hasattr(tax, "cost_center"):
            if tax.cost_center and not _user_has_cost_center_access(tax.cost_center):
                tax.cost_center = user_cost_center
            elif not tax.cost_center:
                tax.cost_center = user_cost_center


def _get_user_default_cost_center():
    """Get the user's default cost center from User Permission."""
    perm = frappe.db.get_value(
        "User Permission",
        {
            "user": frappe.session.user,
            "allow": "Cost Center",
            "is_default": 1,
        },
        "for_value",
    )
    return perm


def _user_has_cost_center_access(cost_center):
    """Check if user has User Permission for this cost center."""
    if not cost_center:
        return True

    return frappe.db.exists(
        "User Permission",
        {
            "user": frappe.session.user,
            "allow": "Cost Center",
            "for_value": cost_center,
        },
    )


# ---------------------------------------------------------------------------
# Branch-default Cash / Bank accounts on Sales Invoice payments
# ---------------------------------------------------------------------------


def _resolve_user_branch(user, company=None, cost_center=None):
    """Pick the most relevant Branch for the user.

    Resolution cascade (first match wins):
      1. Branch Configuration whose company matches the doc and whose
         cost_center child table contains the doc's cost_center.
      2. Branch Configuration whose company matches the doc.
      3. First Branch Configuration the user belongs to (any company).
      4. First User Permission with allow=Branch (fallback when the user
         was wired via standard Frappe permissions but never added to a
         Branch Configuration User row).
    Returns the Branch name or None.
    """
    branches = frappe.get_all(
        "Branch Configuration User",
        filters={"user": user},
        pluck="parent",
    )

    if branches:
        if company:
            same_company = frappe.get_all(
                "Branch Configuration",
                filters={"name": ["in", branches], "company": company},
                pluck="name",
            )
            if same_company:
                if cost_center:
                    with_cc = frappe.get_all(
                        "Branch Configuration Cost Center",
                        filters={"parent": ["in", same_company], "cost_center": cost_center},
                        pluck="parent",
                    )
                    if with_cc:
                        return with_cc[0]
                return same_company[0]
        return branches[0]

    # Fallback: User Permission allow=Branch. Catches users who have
    # been granted branch access via the standard Frappe permission UI
    # but were never added to a Branch Configuration User row.
    up_branches = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Branch"},
        pluck="for_value",
        order_by="is_default desc, modified desc",
    )
    if up_branches:
        return up_branches[0]

    return None


def _branch_mops_by_type(branch_name):
    """Return ({cash:[mops]}, {bank:[mops]}) for this branch.

    Order matches the child-table row order, so the first row of each
    type is the implicit default for that branch.
    """
    cash, bank = [], []
    if not branch_name:
        return cash, bank

    rows = frappe.get_all(
        "Branch Configuration Mode of Payment",
        filters={"parent": branch_name, "parenttype": "Branch Configuration"},
        fields=["mode_of_payment"],
        order_by="idx asc",
    )
    if not rows:
        return cash, bank

    mop_names = [r.mode_of_payment for r in rows if r.mode_of_payment]
    if not mop_names:
        return cash, bank

    type_map = {
        m["name"]: (m.get("type") or "")
        for m in frappe.get_all(
            "Mode of Payment",
            filters={"name": ["in", mop_names]},
            fields=["name", "type"],
        )
    }
    for r in rows:
        t = type_map.get(r.mode_of_payment)
        if t == "Cash":
            cash.append(r.mode_of_payment)
        elif t == "Bank":
            bank.append(r.mode_of_payment)
    return cash, bank


def _mop_account_for_company(mop, company):
    """Read the company-scoped account from `Mode of Payment Account`."""
    if not (mop and company):
        return None
    return frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mop, "company": company},
        "default_account",
    )


def override_payment_accounts_from_branch(doc, method=None):
    """Before validate: constrain Sales Invoice payments[*] to the user's
    Branch Configuration Mode-of-Payment list.

    Each payment row with MoP type Cash or Bank is checked against the
    branch's allowlist for that type:
      - if the row's MoP is in the list → keep it, just resync the account
        from `Mode of Payment Account` for the SI company
      - if the row's MoP is NOT in the list → swap to the first branch
        MoP of the same type (the implicit branch default), then resync
        the account
    BNPL / General / Phone / any other type → untouched.

    Sales Manager / Stock Manager / System Manager / Admin bypass.
    """
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return

    roles = set(frappe.get_roles(user))
    if roles & {"System Manager", "Sales Manager", "Sales Master Manager", "Stock Manager"}:
        return

    payments = doc.get("payments") or []
    if not payments:
        return

    branch = _resolve_user_branch(user, company=doc.company, cost_center=doc.get("cost_center"))
    if not branch:
        return
    cash_mops, bank_mops = _branch_mops_by_type(branch)
    if not cash_mops and not bank_mops:
        return

    # Cache MoP.type lookups for rows we may touch
    type_cache: dict = {}

    def mop_type(name):
        if name not in type_cache:
            type_cache[name] = frappe.db.get_value("Mode of Payment", name, "type") or ""
        return type_cache[name]

    kept_rows = []
    for row in payments:
        mop = getattr(row, "mode_of_payment", None)
        if not mop:
            kept_rows.append(row)
            continue
        t = mop_type(mop)
        if t == "Cash":
            allowed = cash_mops
        elif t == "Bank":
            allowed = bank_mops
        else:
            kept_rows.append(row)
            continue  # BNPL / General / Phone / etc. — leave alone

        if not allowed:
            # Branch explicitly opted out of this type — drop the row.
            continue

        if mop not in allowed:
            row.mode_of_payment = allowed[0]
        new_account = _mop_account_for_company(row.mode_of_payment, doc.company)
        if new_account:
            row.account = new_account
        kept_rows.append(row)

    if len(kept_rows) != len(payments):
        # Reseat the payments table without the removed rows.
        doc.set("payments", [])
        for r in kept_rows:
            doc.append("payments", r.as_dict() if hasattr(r, "as_dict") else r)


@frappe.whitelist()
def get_user_branch_accounts(user: str | None = None, company: str | None = None) -> dict:
    """Return Cash/Bank Mode-of-Payment lists for the user's resolved
    Branch Configuration plus per-MoP account for the SI company.

    Shape:
        {
          "branch": "Jeddah",
          "cash": [{"mop": "Cash", "account": "Cash - CNC"}, ...],
          "bank": [{"mop": "Bank Transfer", "account": "Bank A - CNC"}, ...],
        }

    Used by sales_invoice_doctype.js to prefill / constrain payment rows.
    """
    user = user or frappe.session.user
    if user in ("Administrator", "Guest"):
        return {}

    branch = _resolve_user_branch(user, company=company)
    if not branch:
        return {}

    company = company or frappe.db.get_value("Branch Configuration", branch, "company")
    cash_mops, bank_mops = _branch_mops_by_type(branch)

    def _hydrate(mop_list):
        return [
            {"mop": mop, "account": _mop_account_for_company(mop, company)}
            for mop in mop_list
        ]

    return {
        "branch": branch,
        "cash": _hydrate(cash_mops),
        "bank": _hydrate(bank_mops),
    }


# ---------------------------------------------------------------------------
# Naming series auto-pick from user's Branch
# ---------------------------------------------------------------------------


def _branch_series_override(branch_name: str, doctype: str, is_return: bool) -> str | None:
    """Return the per-doctype series configured on `Branch.custom_naming_series_table`.

    Resolution:
      * Match `parent_doctype == doctype` first.
      * If `is_return=True` AND a row with `use_for_return=1` exists, prefer that row.
      * Otherwise fall back to a row with `use_for_return=0`.
      * Return None when no row matches.
    """
    if not branch_name:
        return None
    rows = frappe.get_all(
        "Branch Naming Series",
        filters={
            "parent": branch_name,
            "parenttype": "Branch",
            "parent_doctype": doctype,
        },
        fields=["naming_series", "use_for_return"],
        order_by="idx asc",
    )
    if not rows:
        return None

    if is_return:
        for r in rows:
            if r.use_for_return:
                return (r.naming_series or "").strip() or None
    for r in rows:
        if not r.use_for_return:
            return (r.naming_series or "").strip() or None
    # Last resort — any row, even one tagged for return when the doc is non-return.
    return (rows[0].naming_series or "").strip() or None


def set_naming_series_from_branch(doc, method=None):
    """Before insert: prefill / override `naming_series` based on the user's Branch.

    Resolution:
      1. Branch's per-doctype `custom_naming_series_table` row matching
         `doc.doctype` and (if applicable) `doc.is_return`.
      2. Branch's `custom_doc_prefix` -> "<PREFIX>.YYYY.-.####".

    OVERRIDES form-prefilled naming_series when the current value does
    not carry the resolved branch prefix. Frappe's form auto-fills
    `naming_series` to the doctype's first option (e.g.
    `ACC-SINV-.YYYY.-` on Sales Invoice) before our hook runs — without
    the override branch users would always end up on the standard
    series. Manager + Admin roles are bypassed so they can pick a
    series manually.

    No-op for Administrator + Guest, for users with no resolvable
    branch, or when the doctype has no naming_series field.
    """
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return
    roles = set(frappe.get_roles(user))
    if roles & {"System Manager", "Stock Manager", "Sales Manager", "Sales Master Manager"}:
        # Trusted roles keep their manual pick.
        return
    if not doc.meta.get_field("naming_series"):
        return

    branch_name = _resolve_user_branch(
        user,
        company=doc.get("company"),
        cost_center=doc.get("cost_center"),
    )
    if not branch_name:
        return

    is_return = bool(doc.get("is_return"))
    series = _branch_series_override(branch_name, doc.doctype, is_return)
    if not series:
        prefix = (frappe.db.get_value("Branch", branch_name, "custom_doc_prefix") or "").strip()
        if not prefix:
            return
        series = f"{prefix}.YYYY.-.####"

    # If the current naming_series already starts with the resolved
    # branch's prefix (or matches an explicit branch override row),
    # keep it — operator may have picked a slightly different variant
    # of the branch series. Otherwise OVERRIDE the form pre-fill.
    current = (doc.get("naming_series") or "").strip()
    if current:
        prefix_only = (frappe.db.get_value("Branch", branch_name, "custom_doc_prefix") or "").strip()
        if prefix_only and current.upper().startswith(prefix_only.upper()):
            return
        if current == series:
            return
        # Otherwise fall through and override.

    # Append the series to the field options if not already present so
    # the value validates. `naming_series` field stores newline-delimited
    # options at the doctype/Property Setter level.
    try:
        meta = frappe.get_meta(doc.doctype)
        field = meta.get_field("naming_series")
        opts = (field.options or "").split("\n") if field else []
        if series not in opts:
            new_opts = "\n".join([series] + [o for o in opts if o])
            ps_name = frappe.db.get_value(
                "Property Setter",
                {
                    "doc_type": doc.doctype,
                    "field_name": "naming_series",
                    "property": "options",
                },
                "name",
            )
            if ps_name:
                frappe.db.set_value("Property Setter", ps_name, "value", new_opts)
            else:
                frappe.get_doc({
                    "doctype": "Property Setter",
                    "doctype_or_field": "DocField",
                    "doc_type": doc.doctype,
                    "field_name": "naming_series",
                    "property": "options",
                    "property_type": "Text",
                    "value": new_opts,
                }).insert(ignore_permissions=True)
            frappe.clear_cache(doctype=doc.doctype)
    except Exception:
        # Don't block doc insert on a metadata-update failure; just leave
        # naming_series empty and let the user pick manually.
        frappe.log_error(
            frappe.get_traceback(),
            f"rmax_custom: naming_series option append failed for {doc.doctype}",
        )
        return

    doc.naming_series = series


# ---------------------------------------------------------------------------
# Suppress auto-filled rejected_warehouse on Purchase Receipt
# ---------------------------------------------------------------------------


def clear_rejected_warehouse_when_no_rejection(doc, method=None):
    """Before validate: if no row has rejected_qty > 0, clear every
    rejected_warehouse field (header + each item row).

    Why: when a user has a single Warehouse User Permission, Frappe's
    `frappe.defaults.get_user_defaults("Warehouse")` returns that
    single value and autofills EVERY Warehouse Link field on form load,
    including `rejected_warehouse`. ERPNext's BuyingController then
    cascades the header value onto each item row via
    `reset_default_field_value`. Result: every row ends up with
    `warehouse == rejected_warehouse`. ERPNext's subcontracting
    validation (called via the Purchase Receipt save chain) throws:
    "Row #0: Accepted Warehouse and Rejected Warehouse cannot be same".

    The user is not running a rejection workflow — they accept full
    qty. Clearing rejected_warehouse when no row has `rejected_qty > 0`
    is the safest fix.
    """
    items = doc.get("items") or []
    has_rejection = any(
        cint(getattr(row, "rejected_qty", 0)) > 0 for row in items
    )
    if has_rejection:
        return

    # Only act when the user did NOT explicitly enter rejection
    if doc.get("rejected_warehouse"):
        doc.rejected_warehouse = None
    for row in items:
        if getattr(row, "rejected_warehouse", None):
            row.rejected_warehouse = None


# ---------------------------------------------------------------------------
# Letter Head auto-set from Branch
# ---------------------------------------------------------------------------


def set_letter_head_from_branch(doc, method=None):
    """Before insert: prefill `letter_head` based on the user's Branch.

    Reads `Branch.custom_letter_head` for the resolved branch and sets
    it on the doc only when the field is empty. Lets a user explicitly
    pick a different letter head before save without being overridden.
    """
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return
    if doc.get("letter_head"):
        return
    if not doc.meta.get_field("letter_head"):
        return

    branch_name = _resolve_user_branch(
        user,
        company=doc.get("company"),
        cost_center=doc.get("cost_center"),
    )
    if not branch_name:
        return

    letter_head = frappe.db.get_value("Branch", branch_name, "custom_letter_head")
    if letter_head:
        doc.letter_head = letter_head


# ---------------------------------------------------------------------------
# Prepared By auto-fill
# ---------------------------------------------------------------------------


def set_prepared_by_to_owner(doc, method=None):
    """Before insert: stamp the creator on `custom_prepared_by`.

    Auto-populates the field with `frappe.session.user` so the printed
    invoice's "Prepared By" line shows who created the document.
    Bypassed for Administrator + Guest. Idempotent — does not overwrite
    an already-filled value.
    """
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return
    if not doc.meta.get_field("custom_prepared_by"):
        return
    if doc.get("custom_prepared_by"):
        return
    doc.custom_prepared_by = user
