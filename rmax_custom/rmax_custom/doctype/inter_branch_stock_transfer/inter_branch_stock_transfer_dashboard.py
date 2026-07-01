# Copyright (c) 2026, Enfono and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
    return {
        "fieldname": "custom_source_docname",
        "internal_links": {
            # String format: reads doc.stock_entry on the IBST document directly.
            "Stock Entry": "stock_entry",
        },
        "non_standard_fieldnames": {
            "Delivery Note": "custom_ibst",
        },
        "dynamic_links": {
            "custom_source_docname": ["Inter Branch Stock Transfer", "custom_source_doctype"],
        },
        "transactions": [
            {
                "label": _("Stock"),
                "items": ["Stock Entry"],
            },
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
