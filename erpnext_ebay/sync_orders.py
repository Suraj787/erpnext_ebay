from __future__ import unicode_literals
from datetime import datetime,timedelta
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
from vlog import vwrite
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
    frappe.local.form_dict.count_dict["orders"] = 0
    get_ebay_orders_array = get_ebay_orders()
    for ebay_order in get_ebay_orders_array:
        ebay_item_id = ebay_order.get("TransactionArray").get("Transaction")[0].get("Item").get("ItemID")
        is_item_in_sync = check_ebay_sync_flag_for_item(ebay_item_id)
        if(is_item_in_sync):
            if valid_customer_and_product(ebay_order):
                try:
                    create_order(ebay_order, ebay_settings)
                    frappe.local.form_dict.count_dict["orders"] += 1

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


def sync_cancelled_ebay_orders():
    frappe.local.form_dict.count_dict["orders"] = 0
    for cancelled_ebay_order in get_cancelled_ebay_orders():
        vwrite(cancelled_ebay_order)
def valid_customer_and_product(ebay_order):
    customer_id = ebay_order.get("BuyerUserID")
    if customer_id:
        if not frappe.db.get_value("Customer", {"ebay_customer_id": customer_id}, "name"):
            create_customer(ebay_order, ebay_customer_list=[])
        else:
            create_customer_address(ebay_order, customer_id)
            create_customer_contact(ebay_order, customer_id)

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
