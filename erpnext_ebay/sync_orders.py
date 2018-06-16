from __future__ import unicode_literals
from datetime import datetime,timedelta
import time
import frappe
from frappe import _
from .exceptions import EbayError
from .utils import make_ebay_log
import frappe
from frappe import _
# from .sync_products import make_item
from .sync_customers import create_customer,create_customer_address,create_customer_contact
from frappe.utils import flt, nowdate, cint
from .ebay_item_common_functions import get_oldest_serial_number
from .ebay_requests import get_request, get_filtering_condition
from vlog import vwrite,rwrite
import sys,traceback
# from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice

ebay_settings = frappe.get_doc("Ebay Settings", "Ebay Settings")
if ebay_settings.last_sync_datetime:
    startTimeString = ebay_settings.last_sync_datetime
    startTimeString = startTimeString[:19]
    startTimeObj = datetime.strptime(startTimeString, '%Y-%m-%d %H:%M:%S')
    startTime = (startTimeObj + timedelta(-5)).isoformat()
else:
    startTime = (datetime.now() + timedelta(-5)).isoformat()
endTime = datetime.now().isoformat()

@frappe.whitelist()
def sync_orders():
    sync_ebay_orders()
    # sync_cancelled_ebay_orders()
def get_ebay_orders(ignore_filter_conditions=False):
    ebay_orders = []
    params = {'CreateTimeFrom': startTime, 'CreateTimeTo': endTime, 'OrderStatus': 'Completed'}
    orders = get_request('GetOrders', 'trading', params)
    if orders.get("OrderArray"):
        ebay_orders = orders.get("OrderArray").get("Order")
    return ebay_orders
def get_cancelled_ebay_orders(ignore_filter_conditions=False):
    cancelled_ebay_orders = []
    params = {'CreateTimeFrom': startTime, 'CreateTimeTo': endTime, 'OrderStatus': 'Cancelled'}
    orders = get_request('GetOrders', 'trading', params)
    if orders.get("OrderArray"):
        cancelled_ebay_orders = orders.get("OrderArray").get("Order")
    return cancelled_ebay_orders

def check_ebay_sync_flag_for_item(ebay_product_id):
    sync_flag = False
    sync_flag_query = """select sync_with_ebay from tabItem where ebay_product_id='%s' or ebay_product_id like '%s' or ebay_product_id like '%s' or ebay_product_id like '%s'""" % (ebay_product_id,ebay_product_id+",%","%,"+ebay_product_id+",%","%,"+ebay_product_id)
    for item in frappe.db.sql(sync_flag_query, as_dict=1):
        if item.get("sync_with_ebay"):
            sync_flag = True
        else:
            sync_flag = False
    return sync_flag
def sync_ebay_orders():
    vwrite("in sync_ebay_orders")
    #frappe.local.form_dict.count_dict["orders"] = 0
    get_ebay_orders_array = get_ebay_orders()
    for ebay_order in get_ebay_orders_array:
        ebay_item_id = ebay_order.get("TransactionArray").get("Transaction")[0].get("Item").get("ItemID")
        is_item_in_sync = check_ebay_sync_flag_for_item(ebay_item_id)
        if(is_item_in_sync):
            if valid_customer_and_product(ebay_order):
                try:
                    create_order(ebay_order, ebay_settings)
                    #frappe.local.form_dict.count_dict["orders"] += 1

                except EbayError, e:
                    vwrite("EbayError raised in create_order")
                    vwrite(ebay_order)
                    make_ebay_log(status="Error", method="sync_ebay_orders", message=frappe.get_traceback(),
                                     request_data=ebay_order.get("OrderID"), exception=True)
                except Exception, e:
                    vwrite("Exception raised in create_order")
                    vwrite(e)
                    vwrite(ebay_order)
                    if e.args and e.args[0]:
                        raise e
                    else:
                        make_ebay_log(title=e.message, status="Error", method="sync_ebay_orders",
                                         message=frappe.get_traceback(),
                                         request_data=ebay_order.get("OrderID"), exception=True)
            else:
                vwrite("Not valid customer and product")
        else:
            vwrite("Item not in sync: %s" % ebay_order.get("TransactionArray").get("Transaction")[0].get("Item").get("Title"))
            make_ebay_log(title="%s" % ebay_order.get("TransactionArray").get("Transaction")[0].get("Item").get("Title"), status="Error", method="sync_ebay_orders",
                             request_data=ebay_order.get("OrderID"),message="Sales order item is not in sync with erp. Sales Order: %s " % ebay_order.get(
                                 "OrderID"))

def print_duration(title,start,end):
    diff = str(end-start)
    print "%s :: %s " % (title,diff[5:])

def processCompleted():
    #import os
    duration = 1  # second
    freq = 440  # Hz
    # os.system('play --no-show-progress --null --channels 1 synth %s sine %f' % (duration, freq))

@frappe.whitelist()
def test():
    synced_ebay_prod_ids = []
    individual_qty_params = []
    get_request_items_store = []
    start = datetime.now()
    print "Started @ %s" % str(start)
    try:
        qty_sync_for_variants(synced_ebay_prod_ids,get_request_items_store,individual_qty_params)
    except IndexError:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print "Exception occurred in test"
        traceback.print_exception(exc_type, exc_value, exc_traceback,limit=2, file=sys.stdout)
    end = datetime.now()
    print "Ended @ %s" % str(end)
    print ("Total time: %s" %str(end-start))
    processCompleted()

def get_chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

@frappe.whitelist()
def testi():
    get_request_items_store = []
    sync_ebay_qty_new(get_request_items_store)
    processCompleted()
    
@frappe.whitelist()
def sync_ebay_qty_new(get_request_items_store):
    print "1:in sync_ebay_qty_new"
    synced_ebay_prod_ids = []
    individual_qty_params = []
    items_sql = """ select distinct item_code,ebay_product_id,variant_of from tabItem where sync_with_ebay='1' and sync_qty_with_ebay='1' and has_variants='0' """
    items_res = frappe.db.sql(items_sql, as_dict=1)
    items_res_start = datetime.now()
    for ebay_item in items_res:
        item_code = ebay_item.get("item_code")
        if not ebay_item.get("variant_of"): # for non-variant items
            get_balance_qty_in_erp_start = datetime.now()
            qty_to_be_updated = get_balance_qty_in_erp(item_code)
            get_balance_qty_in_erp_end = datetime.now()
            print_duration("get_balance_qty_in_erp_duration",get_balance_qty_in_erp_start,get_balance_qty_in_erp_end)
            if ebay_item.get("ebay_product_id"):
                for ebay_product_id in ebay_item.get("ebay_product_id").split(','):
                    if qty_to_be_updated<0:
                        qty_to_be_updated = 0
                    if qty_to_be_updated>5:
                        qty_to_be_updated = 5
                    update_qty_in_ebay_site(ebay_product_id,qty_to_be_updated,synced_ebay_prod_ids,individual_qty_params)
    print individual_qty_params
    chunks = list(get_chunks(individual_qty_params, 4))
    for chunk in chunks:
        reviseInventoryStatus = get_request('ReviseInventoryStatus','trading',{ 'InventoryStatus': chunk })
        print reviseInventoryStatus
    # reviseInventoryStatus = get_request('ReviseInventoryStatus','trading',{ 'InventoryStatus': individual_qty_params })
        
    print "Done revising..."
    items_res_end = datetime.now()
    print_duration("items_res_duration",items_res_start,items_res_end)		
    return False
        # else: # for variant items
            # update_variant_qty_get_model(item_code,ebay_item,synced_ebay_prod_ids)
            
            # qty_to_be_updated = get_balance_qty_in_erp_for_variant_item(item_code)
    synced_ebay_prod_ids = []
    qty_sync_for_variants(synced_ebay_prod_ids,get_request_items_store,individual_qty_params)

def qty_sync_for_variants(synced_ebay_prod_ids,get_request_items_store,individual_qty_params):
    print "1:in qty_sync_for_variants"
    # get all variants of item_template (Refurbished Lenovo Thinkpad variants)
    templates_sql = """ select distinct item_code,ebay_product_id,variant_of from tabItem where sync_with_ebay='1' and sync_qty_with_ebay='1' and has_variants='1'"""
    templates_sql_start = datetime.now()
    unified_params = []
    for item_template in frappe.db.sql(templates_sql, as_dict=1):
        print "2:for templates_sql"
        # get all variants item_code of the template
        all_variants_sql = """ select item_code from tabItem where variant_of='%s' """ % item_template.get("item_code")
        all_variants_sql_start = datetime.now()
        for variant_item in frappe.db.sql(all_variants_sql, as_dict=1):
            print "3:for all_variants_sql"
            # get the attribute value of this code that are not replaceable e.g T440, Core I5, 15" inch etc into an array
            non_replaceable_attr_vals_sql = """ select iva.attribute_value from `tabItem Variant Attribute` iva inner join `tabItem Attribute` ia on iva.attribute = ia.attribute_name where ia.is_replacable = "0" and iva.parent = '%s'""" % variant_item.get("item_code")
            non_replaceable_attr_vals = []
            for nrav in frappe.db.sql(non_replaceable_attr_vals_sql, as_dict=1):
                non_replaceable_attr_vals.append(nrav.get("attribute_value"))
            # Create the where_string to be added in sql
            where_string = ""
            for attribute in non_replaceable_attr_vals:
                where_string += " and item_code like %s " % ('\'%'+attribute+'%\'')
            # Prepare the below query to get the balance
            bal_sql = """ select sum(actual_qty) as bal_qty from `tabStock Ledger Entry` where item_code in (select distinct item_code from  `tabItem Variant Attribute` iva inner join tabItem i on i.item_code = iva.parent where i.variant_of ='%s' %s and warehouse like '%s' )""" %(item_template.get("item_code"),where_string,ebay_settings.warehouse[:-6]+'%')
            bal_sql_start = datetime.now()
            for bal_qty in frappe.db.sql(bal_sql, as_dict=1):
                print "4:for bal_sql"
                if bal_qty.get("bal_qty"):
                    qty_to_be_updated = bal_qty.get("bal_qty")
                    # rwrite(variant_item.get("item_code"))
                    # rwrite(" if Balance Qty in ERP: %s" % qty_to_be_updated)
                else:
                    qty_to_be_updated = 0
                    # rwrite(variant_item.get("item_code"))
                    # rwrite(" else Balance Qty in ERP: %s" % qty_to_be_updated)
                #  get ebay_product_ids
                ebay_prod_ids = []
                ebay_prod_ids = ebay_prod_ids + (get_ebay_product_id_from_template(variant_item.get("item_code")).split(','))
                ebay_prod_ids = filter(None, ebay_prod_ids)
                if qty_to_be_updated<0:
                    qty_to_be_updated = 0
                if qty_to_be_updated>5:
                    qty_to_be_updated = 5
                ebay_prod_ids_start = datetime.now()
                for ebay_product_id in ebay_prod_ids:
                    ebay_id_present = False
                    for param in unified_params:
                        if param.get("Item") and  param.get("Item").get("ItemID")==ebay_product_id:
                            ebay_id_present = True
                    try:
                        print "5:for ebay_prod_ids"
                        params_res = update_variant_qty_in_ebay_site_new(ebay_product_id,qty_to_be_updated,variant_item.get("item_code"),synced_ebay_prod_ids,get_request_items_store)
                        if len(unified_params)>0 and ebay_id_present:
                            if (len(unified_params)>50):
                                print(len(unified_params))
                                print unified_params
                                return False
                            p = 0
                            for param in unified_params:
                                if param.get("Item") and  param.get("Item").get("ItemID")==ebay_product_id and len(params_res.get("Item").get("Variations").get("Variation"))>0:
                                    if ebaytwo_id_present:
                                        unified_params[p]["Item"]["Variations"]["Variation"] = param.get("Item").get("Variations").get("Variation") + params_res.get("Item").get("Variations").get("Variation")
                                    else:
                                        unified_params.append(params_res)
                                p = p+1
                                print "len: %s" % str(len(unified_params))
                                print "6:for unified_params"
                        else:
                            if len(params_res.get("Item").get("Variations").get("Variation"))>0:
                                unified_params.append(params_res)
                        l = 0
                        for unified_param in unified_params:
                            if unified_param.get("Item") and len(unified_param.get("Item").get("Variations").get("Variation"))>0:
                                unified_params[l]["Item"]["Variations"]["Variation"] = filter(None,unified_params[l].get("Item").get("Variations").get("Variation"))
                            l = l+1
                    except Exception,e:
                        print "Exception"
                        print e
                        print e.message
                rwrite("ebay_prod_ids")
                rwrite(ebay_prod_ids)
                ebay_prod_ids_end = datetime.now()
                print_duration("ebay_prod_ids_duration",ebay_prod_ids_start,ebay_prod_ids_end)
                ebay_prod_id_sql = """ select ebay_product_id from tabItem where item_code='%s' """ % variant_item.get("item_code")
                rwrite("ebay_prod_id_sql")
                rwrite(ebay_prod_id_sql)
                for ebay_prod_id_res in frappe.db.sql(ebay_prod_id_sql, as_dict=1):
                    if not ebay_prod_id_res:
                        ebay_individual_prod_ids = ebay_prod_id_res.get("ebay_product_id").split(',')
                        for ebay_individual_prod_id in ebay_individual_prod_ids:
                            rwrite("ebay_individual_prod_id: %s" % ebay_individual_prod_id)
                            update_qty_in_ebay_site(ebay_individual_prod_id,qty_to_be_updated,synced_ebay_prod_ids,individual_qty_params)
            bal_sql_end = datetime.now()
            print_duration("bal_sql_duration",bal_sql_start,bal_sql_end)
        all_variants_sql_end = datetime.now()
        print_duration("all_variants_sql_duration",all_variants_sql_start,all_variants_sql_end)
        rwrite("unified_params")
        rwrite(unified_params)
        for unified_param in unified_params:
            reviseFixedPriceItem = get_request('ReviseFixedPriceItem','trading',unified_param)
    templates_sql_end = datetime.now()
    print_duration("templates_sql_duration",templates_sql_start,templates_sql_end)


            
            
def get_ebay_product_id_from_template(item_code):
    ebay_product_id = ""
    ebay_product_id_sql = """ select ebay_product_id from `tabItem` where item_code=(select variant_of from `tabItem` where item_code='%s') """ % item_code
    ebay_product_id_res = frappe.db.sql(ebay_product_id_sql, as_dict=1)
    for ebay_product_id_row in ebay_product_id_res:
        ebay_product_id = ebay_product_id_row.get("ebay_product_id")
    if not ebay_product_id:
        ebay_product_id = ""
    return ebay_product_id

def update_variant_qty_in_ebay_site(ebay_product_id,qty_to_be_updated,model_name,synced_ebay_prod_ids):
    if True or ebay_product_id+model_name not in synced_ebay_prod_ids:
        # rwrite("Updating Variant: %s, Qty: %s" %(ebay_product_id,qty_to_be_updated))
        synced_ebay_prod_ids.append(ebay_product_id+model_name)
        params = {
            'Item': {
                'ItemID':ebay_product_id,
                'Variations': {
                    'Variation': get_item_variation_specifics(ebay_product_id,qty_to_be_updated,model_name)
                }
            }
        }
        # if len(params.get("Item").get("Variations").get("Variation"))>0 and len(params.get("Item").get("Variations").get("Variation")[0].get("VariationSpecifics").get("NameValueList"))>0:
        #     rwrite("ebaysiteparams:variant")
        #     rwrite(params) 
        #     reviseFixedPriceItem = get_request('ReviseFixedPriceItem','trading',params)

            
        # time.sleep(5)
    # params = {
    #     'Item': {
    #         'ItemID':'183226761324',
    #         'Variations': {
    #             'Variation': [{
    #                 'Quantity':'3',
    #                 'VariationSpecifics':{
    #                     'NameValueList': [
    #                         {'Name':'HDD','Value':'No HDD'},
    #                         {'Name':'RAM','Value':'No RAM'}
    #                     ]
    #                 }
    #             }]
    #         }
    #     }
    # }
    # params = {
    #     'Item': {
    #         'ItemID':ebay_product_id,
    #         'Variations': {
    #             'Variation': get_item_variation_specifics(ebay_product_id,qty_to_be_updated,model_name)
    #         }
    #     }
    # }   
    # reviseFixedPriceItem = get_request('ReviseFixedPriceItem','trading',params)
    # time.sleep(10)
    return True

def update_variant_qty_in_ebay_site_new(ebay_product_id,qty_to_be_updated,model_name,synced_ebay_prod_ids,get_request_items_store):
    if ebay_product_id+model_name not in synced_ebay_prod_ids:
        print "5.1:if not in synced_ebay_prod_ids"
        # rwrite("Updating Variant: %s, Qty: %s" %(ebay_product_id,qty_to_be_updated))
        synced_ebay_prod_ids.append(ebay_product_id+model_name)
        get_item_variation_specifics_new_start = datetime.now()
        params = {
            'Item': {
                'ItemID':ebay_product_id,
                'Variations': {
                    'Variation': get_item_variation_specifics_new(ebay_product_id,qty_to_be_updated,model_name,get_request_items_store)
                }
            }
        }
        get_item_variation_specifics_new_end = datetime.now()
        print_duration("get_item_variation_specifics_new_duration",get_item_variation_specifics_new_start,get_item_variation_specifics_new_end)
        if ebay_product_id == "182748911924":
            params['Item']['PaymentMethods'] = ['PaisaPayEscrow', 'COD', 'PaisaPayEscrowEMI']
        # if len(params.get("Item").get("Variations").get("Variation"))>0 and len(params.get("Item").get("Variations").get("Variation")[0].get("VariationSpecifics").get("NameValueList"))>0:
        #     rwrite("ebaysiteparams:variant :: calling ReviseFixedPriceItem")
        #     rwrite(params) 
        #     reviseFixedPriceItem = get_request('ReviseFixedPriceItem','trading',params)
    return params

def is_duplicate_object(name_value_list,name_value):
    for ext_name_value in name_value_list:
        if ext_name_value.get("Name")==name_value.get("Name") and ext_name_value.get("Value")==name_value.get("Value"):
            return False
    return True
def get_item_variation_specifics(item_id,qty_to_be_updated,model_name):
    variations = []
    # rwrite("in get_item_variation_specifics")
    try:
        has_model = False
        item = get_request('GetItem','trading',{'ItemID':item_id})
        for variation in item.get("Item").get("Variations").get("Variation"):
            temp = False
            name_value_list = []
            for name_value in variation.get("VariationSpecifics").get("NameValueList"):
                if "Name" in name_value and name_value.get("Name")=='Choose Model':
                    has_model = True
                    if name_value.get("Value")==model_name:
                        # if is_duplicate_object(name_value_list,name_value):
                        #     name_value_list.append(name_value)
                        temp = True
                if temp:
                    name_value_list.append(name_value)
            if temp:
                variations.append({'Quantity':int(qty_to_be_updated), 'VariationSpecifics':{'NameValueList': name_value_list}})
                        
                # if temp:
                #     name_value_list.append(name_value)

        if not has_model:
            rwrite("no model:: item_id: %s, model_name: %s" % (item_id,model_name))
            variations.append({'Quantity':int(qty_to_be_updated), 'VariationSpecifics':variation.get("VariationSpecifics")})
        # else:
        #     rwrite("has model:: item_id: %s, model_name: %s" % (item_id,model_name))
        #     variations.append({'Quantity':int(qty_to_be_updated), 'VariationSpecifics':{'NameValueList': name_value_list}})
            
    except Exception,e:
        vwrite("Exception occurred for item_id: %s " % item_id)
        # rwrite("Can't update item_id: %s with qty: %s" % (item_id,qty_to_be_updated))
    # rwrite("returning variations")
    # rwrite(variations)
    return variations
def check_if_attribute_matches_combination(attribute,attribute_value,combinations):
    res = False
    if type(combinations) == dict:
        combinations = [combinations]
    for combination in combinations:    
        if combination.get("Name")==attribute and combination.get("Value")==attribute_value:
            # rwrite("in check_if_attribute_matches_combination :: returning True")
            res = True
    return res
def get_item_variation_specifics_new(item_id,qty_to_be_updated,model_name,get_request_items_store):
    variations = []
    if not item_id:
        print "5.1.1:if not item_id"
        return variations
    try:
        has_model = False
        item_in_get_items_store = [item for item in get_request_items_store if item.get(item_id)]
        if len(item_in_get_items_store):
            item = item_in_get_items_store[0].get(item_id)
        else:
            item = get_request('GetItem','trading',{'ItemID':item_id})
            get_request_items_store.append({item_id:item})
        for_variation_start = datetime.now()
        for variation in item.get("Item").get("Variations").get("Variation"):
            temp = False
            name_value_list = []
            ebay_count = (variation.get("VariationSpecifics").get("NameValueList"))
            # rwrite(variation.get("VariationSpecifics").get("NameValueList"))
            variation_name_value_list = variation.get("VariationSpecifics").get("NameValueList")
            if type(variation_name_value_list) == dict:
                variation_name_value_list = [variation_name_value_list]
            for name_value in variation_name_value_list:
                # get attributes for this model_name and compare if they are matching with combination
                erp_attributes_sql = """ select attribute,attribute_value from `tabItem Variant Attribute` where parent='%s' """ % model_name
                erp_count = 0
                match = True
                for erp_attribute in frappe.db.sql(erp_attributes_sql,as_dict=1):
                    matches = check_if_attribute_matches_combination(erp_attribute.get("attribute"),erp_attribute.get("attribute_value"),variation.get("VariationSpecifics").get("NameValueList"))
                    if not matches:
                        match = False
                if match:
                    name_value_list.append(name_value)
            if len(name_value_list)>0:
                variations.append({'Quantity':int(qty_to_be_updated), 'VariationSpecifics':{'NameValueList': name_value_list}})
        for_variation_end = datetime.now()
        print_duration("for_variation_duration",for_variation_start,for_variation_end)
    except Exception,e:
        vwrite("Exception occurred for item_id: %s " % item_id)
        rwrite("Can't update item_id: %s with qty: %s" % (item_id,qty_to_be_updated))
        rwrite(e.message)
    # rwrite("returning variations")
    # rwrite(variations)
    if type(variations) == dict:
        variations = [variations]
    return variations
        
def update_qty_in_ebay_site(ebay_product_id,qty_to_be_updated,synced_ebay_prod_ids,individual_qty_params):
    if ebay_product_id not in synced_ebay_prod_ids:
        # rwrite("Updating Non-Variant: %s, Qty: %s" %(ebay_product_id,qty_to_be_updated))
        synced_ebay_prod_ids.append(ebay_product_id)
    
    params = {
        'InventoryStatus': {'ItemID':ebay_product_id,'Quantity':int(qty_to_be_updated)}
    }
    individual_qty_params.append({'ItemID':ebay_product_id,'Quantity':int(qty_to_be_updated)})
    rwrite("ebaysiteparams:nonvariant")
    rwrite(params)
    #reviseInventoryStatus = get_request('ReviseInventoryStatus','trading',params)
    # time.sleep(10)
    return True
def get_balance_qty_in_erp(item_code):
    stock_sql = """ select sum(actual_qty) as bal_qty from `tabStock Ledger Entry` where warehouse like '%s' and item_code='%s' """ % (ebay_settings.warehouse[:-6]+'%',item_code)
    stock_res = frappe.db.sql(stock_sql, as_dict=1)
    if stock_res[0] and stock_res[0].get("bal_qty"):
        bal_qty = stock_res[0].get("bal_qty")
    else:
        bal_qty = 0
    so_submitted_sql = """ select sum(soi.qty) as so_submitted_qty from `tabSales Order` so inner join `tabSales Order Item` soi on soi.parent = so.name where soi.item_code='%s' and so.status not in ('Draft','Closed','Cancelled','Completed') """ % item_code
    so_submitted_res = frappe.db.sql(so_submitted_sql, as_dict=1)
    if so_submitted_res[0] and so_submitted_res[0].get("so_submitted_qty"):
        so_submitted_count = so_submitted_res[0].get("so_submitted_qty")
    else:
        so_submitted_count = 0
    actual_qty = bal_qty - so_submitted_count
    return actual_qty
def update_variant_qty_get_model(item_code,ebay_item,synced_ebay_prod_ids):
    model = None
    model_sql = """ select attribute_value from `tabItem Variant Attribute` where parent='%s' and attribute like '%s' """ % (item_code,'%Model%')
    model_res = frappe.db.sql(model_sql, as_dict=1)
    if len(model_res)>0:
        # Model available
        model_name = model_res[0].attribute_value
        stock_sql = """ select sum(actual_qty) as bal_qty from `tabStock Ledger Entry` where warehouse like '%s' and item_code like '%s' """ % (ebay_settings.warehouse[:-6]+'%','%'+model_name+'%')
        stock_res = frappe.db.sql(stock_sql, as_dict=1)
        if stock_res[0] and stock_res[0].get("bal_qty"):
            bal_qty = stock_res[0].get("bal_qty")
        else:
            bal_qty = 0
        so_submitted_sql = """ select sum(soi.qty) as so_submitted_qty from `tabSales Order` so inner join `tabSales Order Item` soi on soi.parent = so.name where soi.item_code like '%s' and so.status not in ('Draft','Closed','Cancelled','Completed') """ % ('%'+model_name+'%')
        so_submitted_res = frappe.db.sql(so_submitted_sql, as_dict=1)
        if so_submitted_res[0] and so_submitted_res[0].get("so_submitted_qty"):
            so_submitted_count = so_submitted_res[0].get("so_submitted_qty")
        else:
            so_submitted_count = 0
        actual_qty = bal_qty - so_submitted_count
        if actual_qty > 5:
            actual_qty = 5  
        #  get ebay_product_ids
        ebay_prod_ids = []
        if ebay_item.get("ebay_product_id"):
            ebay_prod_ids = ebay_prod_ids + (ebay_item.get("ebay_product_id")).split(',')
        ebay_prod_ids = ebay_prod_ids + (get_ebay_product_id_from_template(item_code).split(','))
        if actual_qty<0:
            actual_qty = 0
        for ebay_product_id in ebay_prod_ids:
            update_variant_qty_in_ebay_site(ebay_product_id,actual_qty,model_name,synced_ebay_prod_ids)
    else:# def get_balance_qty_in_erp_for_variant_item(item_code):
        # Model unavailable
        match_item = frappe.db.get_value("Item", {"item_code": item_code}, "variant_of")
        rwrite("No model found for item_code: %s" % item_code)
        stock_sql = """ select sum(actual_qty) as bal_qty from `tabStock Ledger Entry` where warehouse like '%s' and item_code like '%s' """ % (ebay_settings.warehouse[:-6]+'%','%'+match_item+'%')
        stock_res = frappe.db.sql(stock_sql, as_dict=1)
        if stock_res[0] and stock_res[0].get("bal_qty"):
            bal_qty = stock_res[0].get("bal_qty")
        else:
            bal_qty = 0
        so_submitted_sql = """ select sum(soi.qty) as so_submitted_qty from `tabSales Order` so inner join `tabSales Order Item` soi on soi.parent = so.name where soi.item_code like '%s' and so.status not in ('Draft','Closed','Cancelled','Completed') """ % ('%'+match_item+'%')
        so_submitted_res = frappe.db.sql(so_submitted_sql, as_dict=1)
        if so_submitted_res[0] and so_submitted_res[0].get("so_submitted_qty"):
            so_submitted_count = so_submitted_res[0].get("so_submitted_qty")
        else:
            so_submitted_count = 0
        actual_qty = bal_qty - so_submitted_count
        if actual_qty > 5:
            actual_qty = 5  
        #  get ebay_product_ids
        ebay_prod_ids = []
        if ebay_item.get("ebay_product_id"):
            ebay_prod_ids = ebay_prod_ids + (ebay_item.get("ebay_product_id")).split(',')
        ebay_prod_ids = ebay_prod_ids + (get_ebay_product_id_from_template(item_code).split(','))
        if actual_qty<0:
            actual_qty = 0
        for ebay_product_id in ebay_prod_ids:
            update_variant_qty_in_ebay_site(ebay_product_id,actual_qty,"",synced_ebay_prod_ids)
    
def sync_cancelled_ebay_orders():
    frappe.local.form_dict.count_dict["orders"] = 0
    for cancelled_ebay_order in get_cancelled_ebay_orders():
        vwrite(cancelled_ebay_order)
def valid_customer_and_product(ebay_order):
    customer_id = ebay_order.get("BuyerUserID")
    if customer_id:
        if not frappe.db.get_value("Customer", {"ebay_customer_id": customer_id}, "name"):
            customer = create_customer(ebay_order, ebay_customer_list=[])
            if not customer:
                return False
        else:
            address_result = create_customer_address(ebay_order, customer_id)
            if not address_result:
                return False
            contact_result = create_customer_contact(ebay_order, customer_id)
            if not contact_result:
                return False

    else:
        raise _("Customer is mandatory to create order")

    warehouse = frappe.get_doc("Ebay Settings", "Ebay Settings").warehouse
    return True
    for item in ebay_order.get("line_items"):
        if not frappe.db.get_value("Item", {"ebay_product_id": item.get("product_id")}, "name"):
            item = get_request("/admin/products/{}.json".format(item.get("product_id")))["product"]
            make_item(warehouse, item, shopify_item_list=[])

    return True


def create_order(ebay_order, ebay_settings, company=None):
    so = create_sales_order(ebay_order, ebay_settings, company)
    # if ebay_order.get("financial_status") == "paid" and cint(ebay_settings.sync_sales_invoice):
    #     create_sales_invoice(ebay_order, ebay_settings, so)
    #
    # if ebay_order.get("fulfillments") and cint(ebay_settings.sync_delivery_note):
    #     create_delivery_note(ebay_order, ebay_settings, so)


def create_sales_order(ebay_order, ebay_settings, company=None):
    so = frappe.db.get_value("Sales Order", {"ebay_order_id": ebay_order.get("OrderID")}, "name")
    if not so:
        transaction_date = datetime.strptime(nowdate(), "%Y-%m-%d")
        delivery_date = transaction_date + timedelta(days=4)
        # get oldest serial number and update in tabSales Order
        serial_number = get_oldest_serial_number(ebay_order.get("TransactionArray").get("Transaction")[0].get("Item").get("ItemID")) # sending ebay_product_id
        try:
            if ebay_order.get("CheckoutStatus").get("PaymentMethod")=='COD':
                is_cod = True
            else:
                is_cod = False
            so = frappe.get_doc({
                "doctype": "Sales Order",
                "naming_series": ebay_settings.sales_order_series or "SO-Ebay-",
                "is_cod": is_cod,
                "ebay_order_id": ebay_order.get("OrderID"),
		"ebay_buyer_id": ebay_order.get("BuyerUserID"),
                "customer": frappe.db.get_value("Customer",
                                                {"ebay_customer_id": ebay_order.get("BuyerUserID")}, "name"),
                "delivery_date": delivery_date,
                "transaction_date": ebay_order.get("TransactionArray").get("Transaction")[0].get("CreatedDate")[:10],
                "company": ebay_settings.company,
                "selling_price_list": ebay_settings.price_list,
                "ignore_pricing_rule": 1,
                "items": get_order_items(ebay_order.get("TransactionArray").get("Transaction"), ebay_settings),
                "item_serial_no": serial_number
                # "taxes": get_order_taxes(ebay_order.get("TransactionArray").get("Transaction"), ebay_settings),
                # "apply_discount_on": "Grand Total",
                # "discount_amount": get_discounted_amount(ebay_order),
            })
            so.update({
                "customer_address": ebay_order.get("ShippingAddress").get("Name")+"-Shipping",
                "shipping_address_name":ebay_order.get("ShippingAddress").get("Name")+"-Shipping"
            })
            if company:
                so.update({
                    "company": company,
                    "status": "Draft"
                })
            so.flags.ignore_mandatory = True
            so.save(ignore_permissions=True)
            if("Variation" in ebay_order.get("TransactionArray").get("Transaction")[0]):
                variation_details = get_variation_details(ebay_order.get("TransactionArray").get("Transaction")[0])
                created_so_id = frappe.db.get_value("Sales Order",{"ebay_order_id": ebay_order.get("OrderID")}, "name")
                update_wrnty_in_desc_query = """ update `tabSales Order Item` set description='%s' where parent='%s'""" % (variation_details,created_so_id)
                update_wrnty_in_desc_result = frappe.db.sql(update_wrnty_in_desc_query, as_dict=1)
            # so.submit()
        except EbayError, e:
            vwrite("EbayError raised in create_sales_order")
            vwrite(ebay_order)
            make_ebay_log(title=e.message, status="Error", method="create_sales_order", message=frappe.get_traceback(),
                          request_data=ebay_order.get("OrderID"), exception=True)
        except Exception, e:
            vwrite("Exception raised in create_sales_order")
            vwrite(e)
            vwrite(ebay_order)
            if e.args and e.args[0]:
                raise e
            else:
                make_ebay_log(title=e.message, status="Error", method="create_sales_order",
                              message=frappe.get_traceback(),
                              request_data=ebay_order.get("OrderID"), exception=True)
    else:
        so = frappe.get_doc("Sales Order", so)
    frappe.db.commit()
    return so

def get_variation_details(ebay_order_item):
    variation_details = ""
    attr_list = ebay_order_item.get("Variation").get("VariationSpecifics").get("NameValueList")
    for attr in attr_list:
        variation_details = variation_details + attr.get("Name") + ':' + attr.get("Value") + ' ; '
    return variation_details

# def create_sales_invoice(shopify_order, shopify_settings, so):
#     if not frappe.db.get_value("Sales Invoice", {"shopify_order_id": shopify_order.get("id")}, "name") \
#             and so.docstatus == 1 and not so.per_billed:
#         si = make_sales_invoice(so.name)
#         si.shopify_order_id = shopify_order.get("id")
#         si.naming_series = shopify_settings.sales_invoice_series or "SI-Shopify-"
#         si.flags.ignore_mandatory = True
#         set_cost_center(si.items, shopify_settings.cost_center)
#         si.submit()
#         make_payament_entry_against_sales_invoice(si, shopify_settings)
#         frappe.db.commit()


def set_cost_center(items, cost_center):
    for item in items:
        item.cost_center = cost_center


def make_payament_entry_against_sales_invoice(doc, shopify_settings):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    payemnt_entry = get_payment_entry(doc.doctype, doc.name, bank_account=shopify_settings.cash_bank_account)
    payemnt_entry.flags.ignore_mandatory = True
    payemnt_entry.reference_no = doc.name
    payemnt_entry.reference_date = nowdate()
    payemnt_entry.submit()


def create_delivery_note(shopify_order, shopify_settings, so):
    for fulfillment in shopify_order.get("fulfillments"):
        if not frappe.db.get_value("Delivery Note", {"shopify_fulfillment_id": fulfillment.get("id")}, "name") \
                and so.docstatus == 1:
            dn = make_delivery_note(so.name)
            dn.shopify_order_id = fulfillment.get("order_id")
            dn.shopify_fulfillment_id = fulfillment.get("id")
            dn.naming_series = shopify_settings.delivery_note_series or "DN-Shopify-"
            dn.items = get_fulfillment_items(dn.items, fulfillment.get("line_items"), shopify_settings)
            dn.flags.ignore_mandatory = True
            dn.save()
            frappe.db.commit()


def get_fulfillment_items(dn_items, fulfillment_items, shopify_settings):
    return [dn_item.update({"qty": item.get("quantity")}) for item in fulfillment_items for dn_item in dn_items \
            if get_item_code(item) == dn_item.item_code]


def get_discounted_amount(order):
    discounted_amount = 0.0
    for discount in order.get("discount_codes"):
        discounted_amount += flt(discount.get("amount"))
    return discounted_amount


def get_order_items(order_items, ebay_settings):
    items = []
    for ebay_item in order_items:
        if('Variation' in ebay_item):
            item_code = get_variant_item_code(ebay_item)
            if item_code == None:
                # check if item is mapped to non-variant item
                item_code = get_item_code(ebay_item)
                if item_code == None:
                    make_ebay_log(title="Variant Item not found", status="Error", method="get_order_items",
                              message="Variant Item not found for %s" %(ebay_item.get("Item").get("ItemID")),request_data=ebay_item.get("Item").get("ItemID"))
        else:
            item_code = get_item_code(ebay_item)
            if item_code == None:
                make_ebay_log(title="Item not found", status="Error", method="get_order_items",
                              message="Item not found for %s" %(ebay_item.get("Item").get("ItemID")),request_data=ebay_item.get("Item").get("ItemID"))
        items.append({
            "item_code": item_code,
            "item_name": ebay_item.get("Item").get("Title"),
            "rate": ebay_item.get("TransactionPrice").get("value"),
            "qty": ebay_item.get("QuantityPurchased"),
            # "stock_uom": ebay_item.get("sku"),
            "warehouse": ebay_settings.warehouse
        })
    return items


def get_item_code(ebay_item):
    # item_code = frappe.db.get_value("Item", {"ebay_variant_id": ebay_item.get("variant_id")}, "item_code")
    item_code = False
    if not item_code:
        # item_code = frappe.db.get_value("Item", {"ebay_product_id": ebay_item.get("Item").get("ItemID")}, "item_code")
        item_id = ebay_item.get("Item").get("ItemID")
        item_code_query = """ select item_code from `tabItem` where ebay_product_id='%s' or ebay_product_id like '%s' or ebay_product_id like '%s' or ebay_product_id like '%s'""" % (item_id,item_id+",%","%,"+item_id+",%","%,"+item_id)
        item_code_result = frappe.db.sql(item_code_query, as_dict=1)
        if len(item_code_result)>1:
            # getting non-variant item - erpnext_ebay/issue#4
            filter_query = """ select item_code from `tabItem` where variant_of is null and (ebay_product_id='%s' or ebay_product_id like '%s' or ebay_product_id like '%s' or ebay_product_id like '%s')""" % (item_id,item_id+",%","%,"+item_id+",%","%,"+item_id)
            filter_result = frappe.db.sql(filter_query, as_dict=1)
            item_code = filter_result[0].get("item_code")
        else:
            if len(item_code_result):
                item_code = item_code_result[0].get("item_code")
    return item_code

def get_variant_item_code(ebay_item):
    # item = frappe.get_doc("Item", {"ebay_product_id": ebay_item.get("Item").get("ItemID")})
    # item_code = item.get("item_code")
    item_id = ebay_item.get("Item").get("ItemID")
    item_code_query = """ select item_code from `tabItem` where ebay_product_id='%s' or ebay_product_id like '%s' or ebay_product_id like '%s' or ebay_product_id like '%s'""" % (
    item_id, item_id+",%", "%,"+item_id+",%", "%,"+item_id)
    item_code_result = frappe.db.sql(item_code_query, as_dict=1)
    if len(item_code_result) > 1:
        # getting non-variant item - erpnext_ebay/issue#4
        filter_query = """ select item_code from `tabItem` where variant_of is null and (ebay_product_id='%s' or ebay_product_id like '%s' or ebay_product_id like '%s' or ebay_product_id like '%s')""" % (
        item_id, item_id + ",%", "%," + item_id + ",%", "%," + item_id)
        filter_result = frappe.db.sql(filter_query, as_dict=1)
        item_code = filter_result[0].get("item_code")
    else:
        item_code = item_code_result[0].get("item_code")
    variant_items_query = """ select item_code from `tabItem` where variant_of='%s'""" % (item_code)
    variant_items_result = frappe.db.sql(variant_items_query, as_dict=1)
    all_variation_specifics = ebay_item.get("Variation").get("VariationSpecifics").get("NameValueList")
    variation_specifics = []
    if (type(all_variation_specifics) is dict):
        if 'warranty' not in all_variation_specifics.get("Name").lower():
            variation_specifics.append(all_variation_specifics)
    else:
        for required_variation_specifics in all_variation_specifics:
            # if required_variation_specifics.get("Name").lower()!='warranty':
            if 'warranty' not in required_variation_specifics.get("Name").lower():
                variation_specifics.append(required_variation_specifics)
    for variant_item in variant_items_result:
        # get records from tabItemVariantAttributes where parent=variant_item
        variant_attributes_query = """ select * from `tabItem Variant Attribute` where parent='%s' and attribute != 'Warranty'""" % (variant_item.get("item_code"))
        variant_attributes_result = frappe.db.sql(variant_attributes_query, as_dict=1)
        # >> ebay may have extra attributes which we won't consider in erp, so removing equal length condition
        # if len(variant_attributes_result)==len(variation_specifics):
        #     # for each variation specific, compare with result row
        #     matched = 0
        #     for variation_specific in variation_specifics:
        #         for variant_attributes_row in variant_attributes_result:
        #             if((variant_attributes_row.get("attribute").lower()==variation_specific.get("Name").lower()) and (variant_attributes_row.get("attribute_value").lower()==variation_specific.get("Value").lower())):
        #                 matched = matched+1
        #             if len(variation_specifics)==matched:
        #                 return variant_item.get("item_code")
        matched = 0
        for variant_attributes_row in variant_attributes_result:
            for variation_specific in variation_specifics:
                if ((variant_attributes_row.get("attribute").lower() == variation_specific.get("Name").lower()) and (
                    variant_attributes_row.get("attribute_value").lower() == variation_specific.get("Value").lower())):
                    matched = matched + 1
        if len(variant_attributes_result) == matched:
            return variant_item.get("item_code")
            # << ebay may have extra attributes which we won't consider in erp, so removing equal length condition
    return None

def get_order_taxes(ebay_order, ebay_settings):
    taxes = []
    return False
    for tax in ebay_order.get("Taxes"):
        taxes.append({
            "charge_type": _("On Net Total"),
            "account_head": get_tax_account_head(tax),
            "description": "{0} - {1}%".format(tax.get("title"), tax.get("rate") * 100.0),
            "rate": tax.get("rate") * 100.00,
            "included_in_print_rate": 1 if ebay_order.get("taxes_included") else 0,
            "cost_center": ebay_settings.cost_center
        })
    return False
    taxes = update_taxes_with_shipping_lines(taxes, ebay_order.get("shipping_lines"), ebay_settings)

    return taxes


def update_taxes_with_shipping_lines(taxes, shipping_lines, shopify_settings):
    for shipping_charge in shipping_lines:
        taxes.append({
            "charge_type": _("Actual"),
            "account_head": get_tax_account_head(shipping_charge),
            "description": shipping_charge["title"],
            "tax_amount": shipping_charge["price"],
            "cost_center": shopify_settings.cost_center
        })

    return taxes


def get_tax_account_head(tax):
    tax_account = frappe.db.get_value("Ebay Tax Account", \
                                      {"parent": "Ebay Settings", "ebay_tax": tax.get("title")}, "tax_account")

    if not tax_account:
        frappe.throw("Tax Account not specified for Ebay Tax {}".format(tax.get("title")))

    return tax_account
###################
# PAISA PAY ID SYNC
###################
def update_paisapay_id():
    params = {'SoldList': {'DurationInDays': 5, 'Include': True, 'OrderStatusFilter': 'All'}}
    orders = get_request('GetMyeBaySelling', 'trading', params)
    for orderTransaction in orders.get("SoldList").get("OrderTransactionArray").get("OrderTransaction"):
        PaisaPayID = orderTransaction.get("Transaction").get("PaisaPayID")
        OrderLineItemID = orderTransaction.get("Transaction").get("OrderLineItemID")
        so = frappe.db.get_value("Sales Order", {"ebay_order_id": OrderLineItemID},"status")
        if so and so == "Draft":
            so = frappe.get_doc("Sales Order", {"ebay_order_id": OrderLineItemID})
            so.ebay_paisapay_id = PaisaPayID
            so.flags.ignore_mandatory = True
            so.save(ignore_permissions=True)
            #so.submit()
            frappe.db.commit()

    return "OK"

