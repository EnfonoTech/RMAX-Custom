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
    """Pick the most relevant Branch Configuration for the user.

    Resolution order:
      1. Branch whose company matches the doc and whose cost_center child
         table contains the doc's cost_center.
      2. Branch whose company matches the doc.
      3. First branch the user belongs to.
    Returns the Branch Configuration name (== branch name) or None.
    """
    branches = frappe.get_all(
        "Branch Configuration User",
        filters={"user": user},
        pluck="parent",
    )
    if not branches:
        return None

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


def _branch_default_accounts(branch_name):
    if not branch_name:
        return None, None
    row = frappe.db.get_value(
        "Branch Configuration",
        branch_name,
        ["cash_account", "bank_account"],
        as_dict=True,
    ) or {}
    return row.get("cash_account"), row.get("bank_account")


def override_payment_accounts_from_branch(doc, method=None):
    """Before validate: rewrite Sales Invoice payments[*].account based on
    the user's Branch Configuration cash / bank account defaults.

    BNPL and any non-Cash/Bank Mode of Payment is left untouched.
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
    cash_account, bank_account = _branch_default_accounts(branch)
    if not cash_account and not bank_account:
        return

    # Cache MoP type lookups (one row per MoP regardless of branch)
    type_cache: dict = {}

    def mop_type(name):
        if name not in type_cache:
            type_cache[name] = frappe.db.get_value("Mode of Payment", name, "type") or ""
        return type_cache[name]

    for row in payments:
        mop = getattr(row, "mode_of_payment", None)
        if not mop:
            continue
        t = mop_type(mop)
        if t == "Cash" and cash_account:
            row.account = cash_account
        elif t == "Bank" and bank_account:
            row.account = bank_account
        # Other types (General / BNPL / Phone / etc.) — untouched.


@frappe.whitelist()
def get_user_branch_accounts(user: str | None = None, company: str | None = None) -> dict:
    """Return {cash, bank} default accounts from the user's resolved Branch
    Configuration. Used by sales_invoice_doctype.js to prefill payment rows.
    """
    user = user or frappe.session.user
    if user in ("Administrator", "Guest"):
        return {}

    branch = _resolve_user_branch(user, company=company)
    if not branch:
        return {}
    cash, bank = _branch_default_accounts(branch)
    return {"cash": cash, "bank": bank, "branch": branch}
