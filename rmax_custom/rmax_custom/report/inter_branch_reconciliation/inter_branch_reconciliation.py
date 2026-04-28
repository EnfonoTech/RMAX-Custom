"""Inter-Branch Reconciliation report.

Matrix view of inter-branch balances. For every from-branch (rows) and
to-branch (columns), shows the net balance owed. Healthy state: each pair
(A→B and B→A) should sum to zero; non-zero diagonal pairs flag a missing
counterparty tag, an unbalanced manual JE, or a timing difference.
"""
from __future__ import annotations

import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    company = filters.get("company") or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw("Please select a Company filter.")

    abbr = frappe.db.get_value("Company", company, "abbr")
    branches = sorted(b.name for b in frappe.get_all("Branch"))

    conds = ["company = %(company)s", "is_cancelled = 0"]
    params: dict = {"company": company, "abbr": f"% - {abbr}"}
    if filters.get("from_date"):
        conds.append("posting_date >= %(from_date)s")
        params["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conds.append("posting_date <= %(to_date)s")
        params["to_date"] = filters["to_date"]

    rows = frappe.db.sql(
        f"""
        SELECT account, branch, SUM(debit) AS dr, SUM(credit) AS cr
        FROM `tabGL Entry`
        WHERE {' AND '.join(conds)}
          AND (account LIKE 'Due from %%' OR account LIKE 'Due to %%')
          AND account LIKE %(abbr)s
        GROUP BY account, branch
        """,
        params,
        as_dict=True,
    )

    matrix: dict[str, dict[str, float]] = {b: {b2: 0.0 for b2 in branches} for b in branches}
    for r in rows:
        acct = r.account
        if not acct.endswith(f" - {abbr}"):
            continue
        body = acct[: -(len(abbr) + 3)]
        if body.startswith("Due from "):
            counterparty = body[len("Due from "):]
        elif body.startswith("Due to "):
            counterparty = body[len("Due to "):]
        else:
            continue
        owner_branch = r.branch
        if not owner_branch or counterparty not in matrix or owner_branch not in matrix:
            continue
        matrix[owner_branch][counterparty] += flt(r.dr) - flt(r.cr)

    columns = [{"label": "From \\ To", "fieldname": "from_branch", "fieldtype": "Data", "width": 180}]
    for b in branches:
        columns.append({"label": b, "fieldname": _safe_field(b), "fieldtype": "Currency", "width": 140})

    data = []
    for b in branches:
        row = {"from_branch": b}
        for b2 in branches:
            row[_safe_field(b2)] = matrix[b][b2]
        data.append(row)

    return columns, data


def _safe_field(branch_name: str) -> str:
    return "br_" + "".join(ch for ch in branch_name.lower() if ch.isalnum())
