app_name = "field_service_management"
app_title = "Field Service Management"
app_publisher = "Aayush Patidar"
app_description = "Field Service Management"
app_email = "aayushpatidar04@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------
app_include_js = [
    "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"
]
app_include_css = [
    "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css"
]


override_whitelisted_methods = {
    'api.login': 'field_service_management.api.login',
    'api.get_maintenance': 'field_service_management.api.get_maintenance',
    'api.get_maintenance_': 'field_service_management.api.get_maintenance_',
    'api.update_spare_item': 'field_service_management.api.update_spare_item',
    'api.start_maintenance_visit': 'field_service_management.api.start_maintenance_visit',
    'api.check_300m_radius': 'field_service_management.api.check_300m_radius',
    'api.update_punch_in_out': 'field_service_management.api.update_punch_in_out',
    'api.update_checktree': 'field_service_management.api.update_checktree',
    'api.live_location': 'field_service_management.api.live_location',
    'api.attachment': 'field_service_management.api.attachment',
    'api.technician_notes': 'field_service_management.api.technician_notes',
    'api.add_symptom_requests': 'field_service_management.api.add_symptom_requests',
    'api.add_reschedule_requests': 'field_service_management.api.add_reschedule_requests',
}

# include js, css files in header of desk.html
# app_include_css = "/assets/field_service_management/css/field_service_management.css"
# app_include_js = "/assets/field_service_management/js/field_service_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/field_service_management/css/field_service_management.css"
# web_include_js = "/assets/field_service_management/js/field_service_management.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "field_service_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

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
# 	"methods": "field_service_management.utils.jinja_methods",
# 	"filters": "field_service_management.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "field_service_management.install.before_install"
# after_install = "field_service_management.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "field_service_management.uninstall.before_uninstall"
# after_uninstall = "field_service_management.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "field_service_management.utils.before_app_install"
# after_app_install = "field_service_management.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "field_service_management.utils.before_app_uninstall"
# after_app_uninstall = "field_service_management.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "field_service_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"field_service_management.tasks.all"
# 	],
# 	"daily": [
# 		"field_service_management.tasks.daily"
# 	],
# 	"hourly": [
# 		"field_service_management.tasks.hourly"
# 	],
# 	"weekly": [
# 		"field_service_management.tasks.weekly"
# 	],
# 	"monthly": [
# 		"field_service_management.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "field_service_management.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "field_service_management.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "field_service_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["field_service_management.utils.before_request"]
# after_request = ["field_service_management.utils.after_request"]

# Job Events
# ----------
# before_job = ["field_service_management.utils.before_job"]
# after_job = ["field_service_management.utils.after_job"]

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
# 	"field_service_management.auth.validate"
# ]
