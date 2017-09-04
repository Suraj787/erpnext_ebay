from __future__ import unicode_literals
from datetime import datetime,timedelta
import frappe
from frappe import _
from .exceptions import EbayError
from .utils import make_ebay_log
import frappe
from frappe import _
# from .sync_products import make_item
from .sync_customers import create_customer
from frappe.utils import flt, nowdate, cint
from .ebay_item_common_functions import get_oldest_serial_number
from .ebay_requests import get_request, get_filtering_condition
from vlog import vwrite
# from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice

ebay_settings = frappe.get_doc("Ebay Settings", "Ebay Settings")
if ebay_settings.last_sync_datetime:
    startTimeString = ebay_settings.last_sync_datetime
    startTimeObj = datetime.strptime(startTimeString, '%Y-%m-%d %H:%M:%S')
    startTime = startTimeObj.isoformat()
else:
    startTime = (datetime.now() + timedelta(-5)).isoformat()
endTime = datetime.now().isoformat()

def sync_orders():
    vwrite("27-1")
    sync_ebay_orders()
    # sync_cancelled_ebay_orders()
def get_ebay_orders(ignore_filter_conditions=False):
    vwrite("27-3")
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
    vwrite(orders.get("OrderArray"))
    if orders.get("OrderArray"):
        cancelled_ebay_orders = orders.get("OrderArray").get("Order")
    return cancelled_ebay_orders

def check_ebay_sync_flag_for_item(ebay_product_id):
    vwrite("27-6")
    sync_flag = False
    sync_flag_query = """select sync_with_ebay from tabItem where ebay_product_id='%s'""" % ebay_product_id
    for item in frappe.db.sql(sync_flag_query, as_dict=1):
        if item.get("sync_with_ebay"):
            sync_flag = True
        else:
            sync_flag = False
    return sync_flag
def sync_ebay_orders():
    vwrite("27-2")
    frappe.local.form_dict.count_dict["orders"] = 0
    get_ebay_orders_array = get_ebay_orders()
    vwrite("27-4")
    vwrite("length: %s" % len(get_ebay_orders_array))
    for ebay_order in get_ebay_orders_array:
        vwrite("27-5")
        ebay_item_id = ebay_order.get("TransactionArray").get("Transaction")[0].get("Item").get("ItemID")
        is_item_in_sync = check_ebay_sync_flag_for_item(ebay_item_id)
        vwrite("27-7")
        if (ebay_item_id == '182695238775'):
            vwrite("For %s is_item_in_sync value is : %s " % (ebay_item_id, is_item_in_sync))
        if(is_item_in_sync):
            vwrite("Item in sync. Creating sales order")
            if valid_customer_and_product(ebay_order):
                try:
                    vwrite("27-9")
                    create_order(ebay_order, ebay_settings)
                    frappe.local.form_dict.count_dict["orders"] += 1

                except EbayError, e:
                    make_ebay_log(status="Error", method="sync_ebay_orders", message=frappe.get_traceback(),
                                     request_data=ebay_order, exception=True)
                except Exception, e:
                    if e.args and e.args[0] and e.args[0].startswith("402"):
                        raise e
                    else:
                        make_ebay_log(title=e.message, status="Error", method="sync_ebay_orders",
                                         message=frappe.get_traceback(),
                                         request_data=ebay_order, exception=True)
            else:
                vwrite("Not valid customer and product")
        else:
            vwrite("Item is not in sync")
            vwrite(ebay_order)
            make_ebay_log(title="Item not in sync with ebaytwo", status="Error", method=frappe.local.form_dict.cmd,
                             message="Sales order item is not in sync with erp. Sales Order: %s " % ebay_order.get(
                                 "OrderID"))


def sync_cancelled_ebay_orders():
    frappe.local.form_dict.count_dict["orders"] = 0
    for cancelled_ebay_order in get_cancelled_ebay_orders():
        vwrite(cancelled_ebay_order)
    vwrite("Cancelled orders end")
def valid_customer_and_product(ebay_order):
    vwrite("27-8")
    customer_id = ebay_order.get("BuyerUserID")
    if customer_id:
        if not frappe.db.get_value("Customer", {"ebay_customer_id": customer_id}, "name"):
            create_customer(ebay_order, ebay_customer_list=[])
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
    vwrite("27-10")
    so = create_sales_order(ebay_order, ebay_settings, company)
    # if ebay_order.get("financial_status") == "paid" and cint(ebay_settings.sync_sales_invoice):
    #     create_sales_invoice(ebay_order, ebay_settings, so)
    #
    # if ebay_order.get("fulfillments") and cint(ebay_settings.sync_delivery_note):
    #     create_delivery_note(ebay_order, ebay_settings, so)


def create_sales_order(ebay_order, ebay_settings, company=None):
    vwrite("27-11")
    so = frappe.db.get_value("Sales Order", {"ebay_order_id": ebay_order.get("OrderID")}, "name")

    if not so:
        vwrite("27-12")
        transaction_date = datetime.strptime(nowdate(), "%Y-%m-%d")
        delivery_date = transaction_date + timedelta(days=4)
        # get oldest serial number and update in tabSales Order
        serial_number = get_oldest_serial_number(ebay_order.get("TransactionArray").get("Transaction")[0].get("Item").get("ItemID")) # sending ebay_product_id
        vwrite("check here")
        vwrite(serial_number)
        try:
            vwrite("27-13")
            so = frappe.get_doc({
                "doctype": "Sales Order",
                "naming_series": ebay_settings.sales_order_series or "SO-Ebay-",
                "ebay_order_id": ebay_order.get("OrderID"),
                "customer": frappe.db.get_value("Customer",
                                                {"ebay_customer_id": ebay_order.get("BuyerUserID")}, "name"),
                "delivery_date": delivery_date,
                "transaction_date": ebay_order.get("TransactionArray").get("Transaction")[0].get("CreatedDate"),
                "company": ebay_settings.company,
                "selling_price_list": ebay_settings.price_list,
                "ignore_pricing_rule": 1,
                "items": get_order_items(ebay_order.get("TransactionArray").get("Transaction"), ebay_settings),
                "item_serial_no": serial_number
                # "taxes": get_order_taxes(ebay_order.get("TransactionArray").get("Transaction"), ebay_settings),
                # "apply_discount_on": "Grand Total",
                # "discount_amount": get_discounted_amount(ebay_order),
            })
            vwrite("27-14")
            if company:
                vwrite("27-15")
                so.update({
                    "company": company,
                    "status": "Draft"
                })
                vwrite("27-16")
            vwrite("27-17")
            so.flags.ignore_mandatory = True
            vwrite("27-18")
            so.save(ignore_permissions=True)
            vwrite("27-19")
            so.submit()
            vwrite("27-20")
        except EbayError, e:
            make_ebay_log(status="Error", method="sync_ebay_orders", message=frappe.get_traceback(),
                          request_data=ebay_order, exception=True)
        except Exception, e:
            if e.args and e.args[0] and e.args[0].startswith("402"):
                raise e
            else:
                make_ebay_log(title=e.message, status="Error", method="sync_ebay_orders",
                              message=frappe.get_traceback(),
                              request_data=ebay_order, exception=True)
    else:
        vwrite("27-21")
        vwrite("Updating sales order")
        so = frappe.get_doc("Sales Order", so)
        vwrite("27-22")
    vwrite("27-23")
    frappe.db.commit()
    vwrite("27-24")
    return so


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
        item_code = get_item_code(ebay_item)
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
        item_code = frappe.db.get_value("Item", {"ebay_product_id": ebay_item.get("Item").get("ItemID")}, "item_code")
    return item_code


def get_order_taxes(ebay_order, ebay_settings):
    taxes = []
    vwrite("^^^")
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
