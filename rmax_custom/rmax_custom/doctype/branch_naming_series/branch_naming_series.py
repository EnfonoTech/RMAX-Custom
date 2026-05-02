# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

# Frappe v15 requires every child-table doctype to ship a controller
# class — even when istable=1 — otherwise migrate raises
# `Module import failed`.

from frappe.model.document import Document


class BranchNamingSeries(Document):
    pass
