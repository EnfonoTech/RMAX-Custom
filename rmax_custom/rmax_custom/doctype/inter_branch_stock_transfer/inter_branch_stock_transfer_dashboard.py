# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
    return {
        # Journal Entry uses custom_source_docname pointing back to the IBST.
        # Delivery Note uses custom_ibst (a hidden Link field set on creation).
        # internal_links is intentionally omitted — it is only for child-table
        # row lookups; using it with a scalar Link field causes AttributeError.
        "fieldname": "custom_source_docname",
        "non_standard_fieldnames": {
            "Delivery Note": "custom_ibst",
        },
        "transactions": [
            {
                "label": _("Accounting"),
                "items": ["Journal Entry"],
            },
            {
                "label": _("Delivery"),
                "items": ["Delivery Note"],
            },
        ],
    }
