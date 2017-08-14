import frappe
from frappe import _
import json, math, time
from .exceptions import EbayError
from ebaysdk.exception import ConnectionError
from ebaysdk.finding import Connection as finding
from ebaysdk.trading import Connection as trading

from erpnext_ebay.vlog import vwrite

def check_api_call_limit(response):
	"""
		This article will show you how to tell your program to take small pauses
		to keep your app a few API calls shy of the API call limit and
		to guard you against a 429 - Too Many Requests error.

		ref : https://docs.shopify.com/api/introduction/api-call-limit
	"""
	if response.headers.get("HTTP_X_EBAY_SHOP_API_CALL_LIMIT") == 39:
		time.sleep(10)    # pause 10 seconds

def get_trading_api():
    settings = get_ebay_settings()
    api = trading(appid=settings.app_id,
                     devid=settings.dev_id,
                     siteid="203",
                     certid=settings.cert_id,
                     token=settings.user_token,
                     config_file=None)
    return api
def get_finding_api():
    settings = get_ebay_settings()
    api = finding(appid=settings.app_id,
                     devid=settings.dev_id,
                     certid=settings.cert_id,
                     token=settings.user_token,
                     config_file=None)
    return api
def get_request(path,apitype,params, settings=None):
    settings = get_ebay_settings()
    api_calls = {'trading':get_trading_api,
                 'finding':get_finding_api}
    try:
        api = api_calls[apitype]()
        # response = api.execute('findItemsAdvanced',{'keywords': 'Hitachi-1-5-Ton-5-Star-Inverter-Split-Air-Conditioner-RAU518IWEA-Copper-White',
        #     'paginationInput': {
        #         'entriesPerPage': '25',
        #         'pageNumber': '1'
        #     },
        # 'sortOrder': 'CurrentPriceHighest'})
        # response = api.execute('GetCategories',{})
        # response = api.execute("GetSellerList",{'EndTimeFrom':'2017-07-01T19:09:02.768Z','EndTimeTo':'2017-08-01T19:09:02.768Z'})
        response = api.execute(path,params)
    except ConnectionError as e:
        vwrite("exception occured")
        vwrite(e)
        vwrite(e.response.dict())
    return response.dict()
	# check_api_call_limit(r)
	# r.raise_for_status()
	# return r.json()
def post_request(path,apitype,params, settings=None):
    vwrite("in post request")
    vwrite(path)
    vwrite(apitype)
    vwrite(params)
    return {"product":{"id":"123456789"}}
def get_ebay_settings():
    d = frappe.get_doc("Ebay Settings")

    if d.app_id:
        # if d.app_type == "Private" and d.password:
        #     d.password = d.get_password()
        return d.as_dict()
    else:
        frappe.throw(_("Ebay store AppId is not configured on Ebay Settings"), EbayError)


def get_filtering_condition():
	ebay_settings = get_ebay_settings()
	if ebay_settings.last_sync_datetime:
		return 'updated_at_min="{}"'.format(ebay_settings.last_sync_datetime)
	return ''

def get_ebay_items(ignore_filter_conditions=False):
	ebay_products = get_request()
	return ebay_products
