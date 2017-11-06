from __future__ import unicode_literals
from datetime import datetime,timedelta
import frappe
from frappe import _
from .exceptions import EbayError
from .utils import make_ebay_log
import frappe
from frappe import _
from frappe.utils import flt, nowdate, cint
from .ebay_requests import get_request, get_filtering_condition
from dlog import dwrite

ebay_settings = frappe.get_doc("Ebay Settings", "Ebay Settings")
if ebay_settings.last_sync_datetime:
    startTimeString = ebay_settings.last_sync_datetime
    startTimeString = startTimeString[:19]
    startTimeObj = datetime.strptime(startTimeString, '%Y-%m-%d %H:%M:%S')
    startTime = (startTimeObj + timedelta(-5)).isoformat()
else:
    startTime = (datetime.now() + timedelta(-5)).isoformat()
endTime = datetime.now().isoformat()

def get_ebay_orders(ignore_filter_conditions=False):
    ebay_orders = []
    params = {'CreateTimeFrom': startTime, 'CreateTimeTo': endTime, 'OrderStatus': 'Completed'}
    orders = get_request('GetOrders', 'trading', params)
    if orders.get("OrderArray"):
        ebay_orders = orders.get("OrderArray").get("Order")
    return ebay_orders

@frappe.whitelist()
def get_active_listing(ignore_filter_conditions=False):
    dwrite("In get_active_listing")
    # params = {'CreateTimeFrom': startTime, 'CreateTimeTo': endTime, 'OrderStatus': 'Completed'}
    params = {'ActiveList':{'Include':True}}
    active_listings = get_request('GetMyeBaySelling', 'trading', params)
    dwrite("response in get_active_listing")
    dwrite(type(active_listings))
    dwrite(active_listings.__dict__)
    items = active_listings.get("ActiveList").get("ItemArray")
    for item in items:
        dwrite("%s ===============================> %s" % (item.get("ItemID"),item.get("Title")))
    return True

@frappe.whitelist()
def enable_is_purchase_item(ignore_filter_conditions=False):
    # enabling is_purchase_item for variants of 'Refurbished Lenovo Thinkpad'
    items = frappe.get_all("Item", fields=["item_code,is_purchase_item"],filters={"variant_of":"Refurbished Lenovo Thinkpad","is_purchase_item":0})
    for item in items:
        variant_item = frappe.get_doc({
                "doctype": "Item",
                "item_code":item.get("item_code")
        })
        dwrite(variant_item.get("is_purchase_item"))
    return True
def get_cancelled_ebay_orders(ignore_filter_conditions=False):
    cancelled_ebay_orders = []
    params = {'CreateTimeFrom': startTime, 'CreateTimeTo': endTime, 'OrderStatus': 'Cancelled'}
    orders = get_request('GetOrders', 'trading', params)
    if orders.get("OrderArray"):
        cancelled_ebay_orders = orders.get("OrderArray").get("Order")
    return cancelled_ebay_orders
