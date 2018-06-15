# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "erpnext_ebay"
app_title = "Erpnext Ebay"
app_publisher = "vwithv1602"
app_description = "Ebay connector for ERPNext"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "vwithv1602@gmail.com"
app_license = "MIT"

fixtures = ["Custom Field"]
# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnext_ebay/css/erpnext_ebay.css"
# app_include_js = "/assets/erpnext_ebay/js/erpnext_ebay.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_ebay/css/erpnext_ebay.css"
# web_include_js = "/assets/erpnext_ebay/js/erpnext_ebay.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "erpnext_ebay.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "erpnext_ebay.install.before_install"
# after_install = "erpnext_ebay.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_ebay.notifications.get_notification_config"

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

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Bin": {
		"on_update": "erpnext_ebay.sync_products.trigger_update_item_stock"
	}
}

# Scheduled Tasks
# ---------------
scheduler_events = {
#	"hourly": [
#		"erpnext_ebay.api.sync_ebay"
#	]
}
# scheduler_events = {
# 	"all": [
# 		"erpnext_ebay.tasks.all"
# 	],
# 	"daily": [
# 		"erpnext_ebay.tasks.daily"
# 	],
# 	"hourly": [
# 		"erpnext_ebay.tasks.hourly"
# 	],
# 	"weekly": [
# 		"erpnext_ebay.tasks.weekly"
# 	]
# 	"monthly": [
# 		"erpnext_ebay.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "erpnext_ebay.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnext_ebay.event.get_events"
# }

