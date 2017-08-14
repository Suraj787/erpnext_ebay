from datetime import datetime,timedelta
import frappe
from cryptography.hazmat.primitives import serialization
from frappe import _
from .exceptions import EbayError
from .utils import make_ebay_log,disable_ebay_sync_for_item
from frappe.utils import cstr,flt,cint, get_files_path
from .ebay_requests import get_request,get_ebay_items,post_request
from .ebay_item_common_functions import get_ebay_category_id_of_item,get_ebay_item_specifics
from vlog import vwrite
import base64, requests, datetime, os
from erpnext.stock.report.stock_balance.stock_balance import execute


def sync_products(price_list, warehouse):
    vwrite("1")
    ebay_item_list = []
    # from ebay to erpnext start******
    # sync_ebay_items(warehouse, ebay_item_list)
    vwrite("sync_ebay_items done.")
    vwrite(ebay_item_list)

    # check if erpnext_ebay premium account for providing critical_ebay_listing functionality
    ebay_settings = frappe.get_doc("Ebay Settings", "Ebay Settings")
    vwrite("Send %s to premium account check and set erpnext_ebay_premium " % (ebay_settings.ebay_user_id))
    erpnext_ebay_premium = False
    critical_ebay_listings = []
    if(erpnext_ebay_premium):
        # generate critical_ebay_listings by checking stock in erp for each ebay_item_list start******
        generate_critical_ebay_listings(ebay_item_list,critical_ebay_listings,price_list,warehouse)
        vwrite('critical ebay listings')
        vwrite(critical_ebay_listings)
        # check stock in erp for each ebay_item_list end******

    # from ebay to erpnext end******
    frappe.local.form_dict.count_dict["products"] = len(ebay_item_list)
    # erpnext to ebay
    sync_erpnext_items(price_list, warehouse, ebay_item_list,critical_ebay_listings)
    # categoryList = get_request('GetCategories','trading',{'CategoryParent':'181586','ViewAllNodes':True})
    # vwrite(categoryList)
    # transactionList = get_request('GetSellerTransactions', 'trading', {})
    # vwrite(transactionList)

def upload_image_to_ebay(image_url):
    vwrite(image_url)
    image_upload = get_request("UploadSiteHostedPictures", "trading", {"ExternalPictureURL": image_url})
    uploaded_image = image_upload["SiteHostedPictureDetails"].get("FullURL")
    return uploaded_image
def generate_critical_ebay_listings(ebay_item_list,critical_ebay_listings,price_list,warehouse):
    for listing in ebay_item_list:
        ebay_product_id_cond = " and ebay_product_id='%s'" % listing
        item_query = """select name, opening_stock, item_code, item_name, item_group, description, stock_uom, ebay_product_id, ebay_category_id, 
                        standard_rate from tabItem where sync_with_ebay=1 and (disabled is null or disabled = 0) %s""" % ebay_product_id_cond
        for item in frappe.db.sql(item_query, as_dict=1):
            qty = frappe.db.get_value("Bin", {"item_code": item.get("item_code"), "warehouse": warehouse}, "actual_qty")
            price = frappe.db.get_value("Item Price", \
                                        {"price_list": price_list, "item_code": item.get("item_code")},
                                        "price_list_rate")
            if qty <= 5:
                vwrite('stock found critical')
                critical_ebay_listings.append(item.get("ebay_product_id"))
                if price != None:
                    increase_price_by_x_percent(item,price)
            else:
                vwrite('stock not critical')
    return critical_ebay_listings

def increase_price_by_x_percent(item,price):
    increase_percent = 0;
    new_price = price + ((price * increase_percent) / 100)
    vwrite('increase_price_by_%d_percent: %f to %f' % (increase_percent, price, new_price))
    item_data = {"Item": {"ItemID": item.get("ebay_product_id"), "PrimaryCategory": {"CategoryID": item.get("ebay_category_id")}, "StartPrice": new_price}}
    reviseEbayItem(item, item_data)
def trigger_update_item_stock(doc, method):
    vwrite("EBAY OK")
    frappe.msgprint(_("Inside ebay_sync_products"))

def sync_ebay_items(warehouse,ebay_item_list):
    get_seller_list(warehouse,ebay_item_list)

def remove_item_if_not_active(itemid,listingStatus, ebay_item_list):
    if listingStatus != 'Active':
        ebay_item_list.remove(itemid)
def get_seller_list(warehouse,ebay_item_list):
    endTime = datetime.datetime.now().isoformat()
    ebay_settings = frappe.get_doc("Ebay Settings", "Ebay Settings")
    if ebay_settings.last_sync_datetime:
        startTime = ebay_settings.last_sync_datetime
    else:
        startTime = (datetime.datetime.now() + timedelta(-120)).isoformat()
    startTime = (datetime.datetime.now() + timedelta(-120)).isoformat()
    vwrite("remove above startTime. This should be there only for development period")
    params = {'StartTimeFrom':startTime,'StartTimeTo':endTime}
    sellerList = get_request('GetSellerList','trading',params)
    vwrite("obtaining seller List")
    vwrite(sellerList)
    # vamc sellerList
    # sellerList = {'Ack': 'Success', 'Timestamp': '2017-07-23T14:06:22.196Z', 'ItemArray': {"Item": [{"ItemID": "182644622850","ListingDetails": {"EndTime": "2017-07-30T12:02:52.000Z","StartTime": "2017-06-30T12:02:52.000Z"}},{"ItemID": "182662935623","ListingDetails": {"EndTime": "2017-08-10T09:43:09.000Z","StartTime": "2017-07-11T09:43:09.000Z"}},{"ItemID": "182673494720","ListingDetails": {"EndTime": "2017-08-17T05:06:20.000Z","StartTime": "2017-07-18T05:06:20.000Z"}}]}, 'ReturnedItemCountActual': '22', 'Version': '1015', 'Build': 'E1015_INTL_APISELLING_18426275_R1', 'PaginationResult': {'TotalNumberOfEntries': '22'}}
    ebayItemsData = sellerList.get("ItemArray").get("Item")
    for item in ebayItemsData:
        ebay_item_list.append(item.get('ItemID'))
        ebay_item_details = get_ebay_item_by_id(item.get('ItemID'))
        vwrite("item")
        vwrite(ebay_item_details)
        listingStatus = ebay_item_details.get("Item").get("SellingStatus").get("ListingStatus")
        remove_item_if_not_active(item.get('ItemID'),listingStatus, ebay_item_list)
        if listingStatus == 'Active':
            make_item(item)
        vwrite("active items in ebay")
        vwrite(ebay_item_list)
def make_item(item):
    # check if erp has ebay item by ebay_product_id
    vwrite("making ebay item in erp")
def get_ebay_item_by_id(ebay_item_id):
    params = {'ItemID':ebay_item_id}
    ebayItem = get_request('GetItem','trading',params)
    return ebayItem

def sync_erpnext_items(price_list, warehouse, ebay_item_list,critical_ebay_listings):
    # erpnext to ebay
    vwrite("2")
    ebay_settings = frappe.get_doc("Ebay Settings", "Ebay Settings")

    last_sync_condition = ""
    if ebay_settings.last_sync_datetime:
        last_sync_condition = "and modified >= '{0}' ".format(ebay_settings.last_sync_datetime)
    item_query = """select name, item_code, item_name, item_group,
    		description, shopify_description, has_variants, stock_uom, image, ebay_product_id,ebay_category_id, 
    		shopify_variant_id, sync_qty_with_shopify, net_weight, weight_uom, default_supplier,_user_tags,standard_rate from tabItem
    		where sync_with_ebay=1 and (variant_of is null or variant_of = '')
    		and (disabled is null or disabled = 0) %s """ % last_sync_condition

    for item in frappe.db.sql(item_query, as_dict=1):
        vwrite("ebay_product_id && ebay_item_list")
        vwrite(item.ebay_product_id)
        vwrite(ebay_item_list)
        vwrite('critical_ebay_listings')
        vwrite(critical_ebay_listings)
        if item.ebay_product_id not in ebay_item_list:
            try:
                if(len(critical_ebay_listings)):
                    vwrite("map existing erpid & %s in log file" % (critical_ebay_listings[0]))

                    get_erpid_query = """select name from tabItem where ebay_product_id= '%s'""" %critical_ebay_listings[0]
                    erp_item_by_ebay_prod_id = frappe.db.sql(get_erpid_query, as_dict=1)
                    vwrite(erp_item_by_ebay_prod_id)
                    vwrite('got erpid')
                    vwrite(item)
                    ebay_erp_item_revise_map_log = frappe.get_doc({
                        "doctype":"Ebay ERP Item Revise Map Log",
                        "from_date": ebay_settings.last_sync_datetime,
                        "to_date": datetime.datetime.now().isoformat(),
                        "erp_id": erp_item_by_ebay_prod_id[0].get("name"),
                        "ebay_product_id": critical_ebay_listings[0],
                        "log_date": datetime.datetime.now().isoformat()
                    })
                    ebay_erp_item_revise_map_log.flags.ignore_mandatory = True
                    ebay_erp_item_revise_map_log.insert(ignore_permissions=True)

                    vwrite("revise item")
                    replace_ebay_item_with_erp_item(item)
                    vwrite("remove from critical list")
                else:
                    # vwrite("syncing below item init")
                    # vwrite(item)
                    sync_item_with_ebay(item, price_list, warehouse)
                    frappe.local.form_dict.count_dict["products"] += 1

            except EbayError, e:
                make_ebay_log(title=e.message, status="Error", method="sync_ebay_items",
                                 message=frappe.get_traceback(),
                                 request_data=item, exception=True)
            except Exception, e:
                make_ebay_log(title=e.message, status="Error", method="sync_ebay_items",
                                 message=frappe.get_traceback(),
                                 request_data=item, exception=True)

def replace_ebay_item_with_erp_item(item):
    vwrite('set params obj and call revise item')

def sync_item_with_ebay(item, price_list, warehouse):
    # erpnext to ebay
    vwrite("3")
    # get image url from database
    serial_item_exists = False
    multiple_serial_item_images_exists = False
    multiple_item_images_exists = False
    # check if item is serialized
    # serialized_query = """ select sn.name as sn_name,dni.serial_no as dni_serial_no from `tabSerial No` sn inner join `tabDelivery Note Item` dni on dni.serial_no<>sn.name where sn.item_code='%s' order by sn.creation asc limit 1""" % item.get("item_code")
    serialized_query = """select sn.name as sn_name from `tabSerial No` sn inner join `tabItem` i on i.item_code=sn.item_code where i.item_code='%s' limit 1""" % item.get("item_code")
    # vwrite("serialized_query")
    # vwrite(serialized_query)
    item_images_obj = []
    for serialized_item in frappe.db.sql(serialized_query, as_dict=1):
        serial_item_exists = True
        # vwrite(serialized_item.get("sn_name"))
        # checking serial_items_images
        serial_item_images_query = """select item_image, parent from `tabItem Images` where parent='%s' and item_image not like %s""" % (serialized_item.get("sn_name"),"'%i.ebayimg.com%'")
        # vwrite("serial_item_images_query")
        # vwrite(serial_item_images_query)
        for serial_item_image in frappe.db.sql(serial_item_images_query, as_dict=1):
            multiple_serial_item_images_exists = False
            # upload serial_item_images to ebay
            uploaded_image = upload_image_to_ebay(serial_item_image.get("item_image"))
            item_images_obj.append(uploaded_image)
    if not multiple_serial_item_images_exists:
        # checking multiple_item_images
        multiple_item_images_query = """select item_image, parent from `tabItem Images` where parent='%s' and item_image not like %s""" % (item.get("item_code"),"'%i.ebayimg.com%'")
        # vwrite("multiple_item_images_query")
        # vwrite(multiple_item_images_query)
        for item_image in frappe.db.sql(multiple_item_images_query, as_dict=1):
            multiple_item_images_exists = False
            # upload item_images to ebay
            uploaded_image = upload_image_to_ebay(item_image.get("item_image"))
            item_images_obj.append(uploaded_image)
    if not (multiple_serial_item_images_exists and multiple_item_images_exists):
        # checking if item image exists
        item_image_query = """select image, parent from `tabItem` where parent='%s' and image not like %s""" % (item.get("item_code"), "'%i.ebayimg.com%'")
        # vwrite("item_image_query")
        # vwrite(item_image_query)
        for image in frappe.db.sql(item_image_query, as_dict=1):
            # upload item_images to ebay
            uploaded_image = upload_image_to_ebay(image.get("image"))
            item_images_obj.append(uploaded_image)
    vwrite("item_images_obj::images that have been uploaded to ebay")
    vwrite(item_images_obj)

    # images_query = """select item_image, parent from `tabItem Images` where parent='%s' and item_image not like '%i.ebayimg.com%'""" % item.get("item_code")
    # for image in frappe.db.sql(images_query, as_dict=1):
    #     image_url = image.get("item_image")
    #     image_parent_item = image.get("parent")
    #     # uploaded_image = upload_image_to_ebay(image_url)
    variant_item_name_list = []
    item_data = { "Item" :
        {
            "Title":item.get("item_name"),
            "Description":item.get("description"),
            "PrimaryCategory":{
                "CategoryID":get_ebay_category_id_of_item(item)
            },
            "StartPrice":item.get("standard_rate"),
            # "CategoryMappingAllowed":"true",
            # "ConditionID":"ConditionID",
            "Country":"IN",
            "Currency":"INR",
            # "DispatchTimeMax":"DispatchTimeMax",
            "ListingDuration":"GTC",
            "ListingType":"FixedPriceItem",
            "PaymentMethods":["PaisaPayEscrow","PaisaPayEscrowEMI","COD"],
            # "PayPalEmailAddress":"seller@usedyetnew.com",
            "PictureDetails":{
                "PictureURL":item_images_obj
            },
            "PostalCode":"500084",
            "Quantity":"1",
            "ProductListingDetails":{
                "UPC": "Does not apply"
            },
            "Site":"India",
            "ConditionID":"1000",
            "ShippingDetails": {
                "ShippingDiscountProfileID": "0",
                "InternationalShippingDiscountProfileID": "0",
                "ShippingServiceOptions": {
                    # "ShippingServiceCost": {
                    #     "_currencyID": "INR",
                    #     "value": "0.0"
                    # },
                    "ShippingServicePriority": "1",
                    # "ShippingServiceAdditionalCost": {
                    #     "_currencyID": "INR",
                    #     "value": "0.0"
                    # },
                    "ShippingService": "IN_Surface",
                    "FreeShipping": "true",
                    "ExpeditedService": "false"
                },
                # "CalculatedShippingRate": {
                #     "WeightMinor": {
                #         "_unit": "oz",
                #         "_measurementSystem": "English",
                #         "value": "0"
                #     },
                #     "WeightMajor": {
                #         "_unit": "lbs",
                #         "_measurementSystem": "English",
                #         "value": "0"
                #     }
                # },
                "SellerExcludeShipToLocationsPreference": "true",
                "ShippingType": "Flat",
                "ThirdPartyCheckout": "false",
                "ApplyShippingDiscount": "false",
                "SalesTax": {
                    "SalesTaxPercent": "0.0",
                    "ShippingIncludedInTax": "false"
                }
            },
            "ItemSpecifics":
            {
                "NameValueList": get_ebay_item_specifics(item)
            }
        }
    }
    return False
    vwrite("item_data")
    vwrite(item_data)

    erp_item = frappe.get_doc("Item", item.get("name"))
    erp_item.flags.ignore_mandatory = True
    if not item.get("ebay_product_id"):
        vwrite("creating new listing for the item")
        create_new_item_to_ebay(item, item_data, erp_item, variant_item_name_list)
    else:
        vwrite("ebay_product_id present in item")
        vwrite(item.get("ebay_product_id"))
        # item_data["product"]["id"] = item.get("ebay_product_id")
        vwrite(item_data)
        try:
            reviseEbayItem(item,item_data)
            vwrite("Make put request to update ebay item")

        except requests.exceptions.HTTPError, e:
            if e.args[0] and e.args[0].startswith("404"):
                # if frappe.db.get_value("Ebay Settings", "Ebay Settings", "if_not_exists_create_item_to_ebay"):
                if True:
                    item_data["product"]["id"] = ''
                    create_new_item_to_ebay(item, item_data, erp_item, variant_item_name_list)
                else:
                    disable_ebay_sync_for_item(erp_item)
            else:
                raise e
    # sync_item_image(erp_item)
    frappe.db.commit()

def create_new_item_to_ebay(item, item_data, erp_item, variant_item_name_list):
    vwrite("listing new item will cost you")
    vwrite(item_data)
    # image_url = "" get image url from database

    # image_upload = get_request("UploadSiteHostedPictures","trading",{"ExternalPictureURL":image_url})
    # uploaded_image = image_upload["SiteHostedPictureDetails"].get("FullURL")
    # item_data["Item"]["PictureDetails"]["PictureURL"] = uploaded_image

    # ******for adding/listing new item uncomment the below code start******
    new_item = get_request("AddItem","trading",item_data)
    vwrite("new_item")
    vwrite(new_item)
    erp_item.ebay_product_id = new_item.get("ItemID")
    vwrite(new_item.get("ItemID"))
    erp_item.save()
    vwrite("Listing new item successful with ebay_product_id: %s" % (new_item.get("ItemID")))
    # ******for adding/listing new item uncomment the below code end******

def reviseEbayItem(item,item_data):
    # revising/updating existing item
    vwrite("revising/updating existing item")
    # item_details = {
    #     'item': {
    #         'ItemID': item.get("ebay_product_id"),
    #         # 'StartPrice': item.get("standard_rate"),
    #         'StartPrice': 65000.0,
    #         'Quantity':'1',
    #         'PrimaryCategory': {
    #             'CategoryID':item.get("ebay_category_id")
    #         }
    #         # 'Variations': {
    #         #     'Variation': {
    #         #         'Quantity': '1'
    #         #     }
    #         # }
    #     }
    # }
    # response = get_request("ReviseItem","trading",item_data)
    vwrite("revising successfull but you need to uncomment the above line to see it in action")
    # vwrite(response)

def get_weight_in_grams(weight, weight_uom):
	convert_to_gram = {
		"kg": 1000,
		"lb": 453.592,
		"oz": 28.3495,
		"g": 1
	}

	return weight * convert_to_gram[weight_uom.lower()]