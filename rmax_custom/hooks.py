app_name = "rmax_custom"
app_title = "Rmax Custom"
app_publisher = "Enfono"
app_description = "Customisation For RMAX"
app_email = "ramees@enfono.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "rmax_custom",
# 		"logo": "/assets/rmax_custom/logo.png",
# 		"title": "Rmax Custom",
# 		"route": "/rmax_custom",
# 		"has_permission": "rmax_custom.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/rmax_custom/css/rmax_custom.css"
app_include_js = [
    "/assets/rmax_custom/js/enter_navigation_global.js",
    "/assets/rmax_custom/js/warehouse_stock_popup.js",
    "/assets/rmax_custom/js/sales_invoice_pos_total_popup.js",
    "/assets/rmax_custom/js/sales_invoice_popup.js",
    "/assets/rmax_custom/js/create_customer.js",
    "/assets/rmax_custom/js/create_multiple_supplier.js",
    "/assets/rmax_custom/js/materiel_request.js",
    "/assets/rmax_custom/js/vat_validation.js",
    "/assets/rmax_custom/js/contact_validation.js",
    "/assets/rmax_custom/js/item_branch_user.js"
]



# include js, css files in header of web template
# web_include_css = "/assets/rmax_custom/css/rmax_custom.css"
# web_include_js = "/assets/rmax_custom/js/rmax_custom.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "rmax_custom/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Quotation": "rmax_custom/custom_scripts/quotation/quotation.js",
    "Purchase Receipt": "public/js/purchase receipt.js",
    "Landed Cost Voucher": "public/js/landed_cost_voucher.js"
}
doctype_list_js = {
    "Purchase Receipt": "public/js/purchase_receipt_list.js",
    "Material Request": "public/js/material_request_list.js",
    "Sales Invoice": "public/js/sales_invoice_list.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "rmax_custom/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "rmax_custom.utils.jinja_methods",
# 	"filters": "rmax_custom.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "rmax_custom.install.before_install"
# after_install = "rmax_custom.install.after_install"

after_migrate = ["rmax_custom.setup.after_migrate"]

# Uninstallation
# ------------

# before_uninstall = "rmax_custom.uninstall.before_uninstall"
# after_uninstall = "rmax_custom.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "rmax_custom.utils.before_app_install"
# after_app_install = "rmax_custom.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "rmax_custom.utils.before_app_uninstall"
# after_app_uninstall = "rmax_custom.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "rmax_custom.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Sales Invoice": "rmax_custom.branch_filters.si_permission_query",
	"Purchase Invoice": "rmax_custom.branch_filters.pi_permission_query",
	"Delivery Note": "rmax_custom.branch_filters.dn_permission_query",
	"Purchase Receipt": "rmax_custom.branch_filters.pr_permission_query",
	"Payment Entry": "rmax_custom.branch_filters.pe_permission_query",
	"Quotation": "rmax_custom.branch_filters.quotation_permission_query",
}

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Landed Cost Voucher": "rmax_custom.overrides.landed_cost_voucher.LandedCostVoucher"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Sales Invoice": {
		"before_validate": "rmax_custom.branch_defaults.override_cost_center_from_branch",
		"on_submit": "rmax_custom.inter_company.sales_invoice_on_submit",
	},
	"Purchase Invoice": {
		"before_validate": "rmax_custom.branch_defaults.override_cost_center_from_branch",
	},
	"Payment Entry": {
		"before_validate": "rmax_custom.branch_defaults.override_cost_center_from_branch",
	},
	"Delivery Note": {
		"before_validate": "rmax_custom.branch_defaults.override_cost_center_from_branch",
	},
	"Purchase Receipt": {
		"before_validate": "rmax_custom.branch_defaults.override_cost_center_from_branch",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"rmax_custom.tasks.all"
# 	],
# 	"daily": [
# 		"rmax_custom.tasks.daily"
# 	],
# 	"hourly": [
# 		"rmax_custom.tasks.hourly"
# 	],
# 	"weekly": [
# 		"rmax_custom.tasks.weekly"
# 	],
# 	"monthly": [
# 		"rmax_custom.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "rmax_custom.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "rmax_custom.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "rmax_custom.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["rmax_custom.utils.before_request"]
# after_request = ["rmax_custom.utils.after_request"]

# Job Events
# ----------
# before_job = ["rmax_custom.utils.before_job"]
# after_job = ["rmax_custom.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"rmax_custom.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = [
    "Workflow",
    "Workflow State",
    "Workflow Action Master",
    {
        "dt": "Role",
        "filters": [["name", "in", ["Branch User"]]]
    },
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    # Sales Invoice
                    "Sales Invoice-custom_payment_mode",
                    "Sales Invoice-custom_inter_company_branch",

                    # Sales Invoice Item
                    "Sales Invoice Item-total_vat_linewise",

    
                    # Quotation
                    "Quotation-custom_payment_mode",

                    # Quotation Item
                    "Quotation Item-total_vat_linewise",

                    # Landed Cost Voucher (CBM distribution when Distribute Manually)
                    "Landed Cost Voucher-custom_distribute_by_cbm",
                    # Landed Cost Item (CBM per item)
                    "Landed Cost Item-custom_cbm",
                    "Customer-custom_vat_registration_number",

                    # Material Request
                    "Material Request-custom_is_urgent",
                ]
            ]
        ]
    },
    {
        "dt": "Property Setter",
        "filters": [
            [
                "name",
                "in",
                [
                    "Material Request Item-warehouse-hidden",
                    "Material Request Item-from_warehouse-hidden",
                    "Material Request Item-schedule_date-reqd",
                    "Material Request Item-schedule_date-hidden",
                    "Material Request Item-schedule_date-default",
                    "Material Request-schedule_date-hidden",
                    "Landed Cost Item-qty-columns",
                    "Material Request-material_request_type-default",
                    "Customer-customer_type-options",

                    # Sales Invoice list view filters
                    "Sales Invoice-grand_total-in_standard_filter",
                    "Sales Invoice-total_qty-in_standard_filter",
                    "Sales Invoice-contact_mobile-in_standard_filter",
                ]
            ]
        ]
    }
]
