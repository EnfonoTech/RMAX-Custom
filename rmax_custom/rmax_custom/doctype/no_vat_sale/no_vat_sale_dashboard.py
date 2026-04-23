# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return {
		"fieldname": "custom_no_vat_sale",
		"transactions": [
			{
				"label": _("References"),
				"items": ["Journal Entry", "Stock Entry"],
			},
		],
	}
