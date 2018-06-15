from __future__ import unicode_literals
import frappe
from frappe import _
from .exceptions import EbayError
from .sync_products import sync_products
from .sync_orders import sync_orders,sync_ebay_qty,update_paisapay_id
from .utils import disable_ebay_sync_on_exception, make_ebay_log
from frappe.utils.background_jobs import enqueue
from erpnext_ebay.vlog import vwrite
from datetime import datetime,timedelta
from .send_feedback_requests import send_ebay_feedback_request
from .ebay_lead_management import lead_status_modifier

@frappe.whitelist()
def sync_ebay():
    #enqueue("erpnext_ebay.api.init_feedback_requests", queue='long')
    enqueue("erpnext_ebay.api.sync_ebay_resources", queue='long')
    # enqueue("erpnext_ebay.api.init_ebay_lead_management", queue='long')
    frappe.msgprint(_("Queued for syncing. It may take a few minutes to an hour if this is your first sync."))
    

@frappe.whitelist()
def init_ebay_lead_management():
    lead_status_modifier()
    
@frappe.whitelist()
def init_feedback_requests():
    ebay_settings = frappe.get_doc("Ebay Settings")
    google_settings = frappe.get_doc("Google Account Setup")
    # make_ebay_log(title="Ebay Feedback Job Queued", status="Queued", method=frappe.local.form_dict.cmd,message="Ebay Feedback Job Queued")
    if(ebay_settings.enable_ebay and google_settings.client_id and google_settings.client_secret):
        send_ebay_feedback_request()
    else:
        frappe.msgprint(_("Ebay sync is not enabled or google account setup is incomplete"))
@frappe.whitelist()
def sync_ebay_resources():
    "Enqueue longjob for syncing shopify"
    ebay_settings = frappe.get_doc("Ebay Settings")
    make_ebay_log(title="Ebay Sync Job Queued", status="Queued", method=frappe.local.form_dict.cmd,
                     message="Ebay Sync Job Queued")
    if(ebay_settings.enable_ebay):
        try:
            now_time = frappe.utils.now()
            validate_ebay_settings(ebay_settings)
            frappe.local.form_dict.count_dict = {}
            # sync_products(ebay_settings.price_list, ebay_settings.warehouse)
	    vwrite("starting sync_orders")
            sync_orders()
	    vwrite("ending sync_orders")
            
            make_ebay_log(title="Ebay Sync Completed", status="Success", method=frappe.local.form_dict.cmd,
                             message="Updated. This should come after successful syncing ebay")
            make_ebay_log(title="Ebay Qty Sync Queued", status="Success", method=frappe.local.form_dict.cmd,
                             message="Quantity sync of ebay started.")
            get_request_items_store = []
            try:
                a=1
                #sync_ebay_qty(get_request_items_store)
            except Exception, e:
                vwrite("loopbreak")
                vwrite(e.message)
            make_ebay_log(title="Ebay Qty Sync Completed", status="Success", method=frappe.local.form_dict.cmd,
                             message="Quantity sync of ebay completed.")
            # update_paisapay_id()
            frappe.db.set_value("Ebay Settings", None, "last_sync_datetime", now_time)

        except Exception, e:
            if e.args[0] and hasattr(e.args[0], "startswith") and e.args[0].startswith("402"):
                make_ebay_log(title="Ebay has suspended your account", status="Error",
                                 method="sync_ebay_resources", message=_("""Ebay has suspended your account till
            		you complete the payment. We have disabled ERPNext Ebay Sync. Please enable it once
            		your complete the payment at Ebay."""), exception=True)

                disable_ebay_sync_on_exception()

            else:
                make_ebay_log(title="sync has terminated", status="Error", method="sync_ebay_resources",
                                 message=frappe.get_traceback(), exception=True)
    elif frappe.local.form_dict.cmd == "erpnext_ebay.api.sync_ebay":
        make_ebay_log(
            title="Ebay connector is disabled",
            status="Error",
            method="sync_ebay_resources",
            message=_(
                """Ebay connector is not enabled. Click on 'Connect to Ebay' to connect ERPNext and your Ebay store."""),
            exception=True)

def validate_ebay_settings(ebay_settings):
	"""
		This will validate mandatory fields and access token or app credentials
		by calling validate() of shopify settings.
	"""
	try:
		ebay_settings.save()
	except Exception, e:
		disable_ebay_sync_on_exception()
