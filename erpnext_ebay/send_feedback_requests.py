from __future__ import unicode_literals
from datetime import datetime,timedelta
import frappe
from frappe import _
from .exceptions import EbayError
from .utils import make_ebay_log
from erpnext_ebay.vlog import vwrite
from .ebay_item_common_functions import get_oldest_serial_number
from .ebay_requests import get_request, get_filtering_condition
import json as simplejson
@frappe.whitelist()
def send_ebay_feedback_request():
    feedback_required_ids_from_erp = get_feedback_required_ids_from_erp()

    ## buyers who already took feadback
    params = {"SoldList":{"Include":True,"OrderStatusFilter":"PaidAndShipped"}}
    myebayselling = get_request('GetMyeBaySelling', 'trading', params)
    result = myebayselling.get("SoldList").get("OrderTransactionArray").get("OrderTransaction")
    buyers_already_took_feedback = []
    for transaction in result:
        if transaction.get("Transaction").get("FeedbackReceived"):
            buyers_already_took_feedback.append(transaction.get("Transaction").get("Buyer").get("UserID"))

    ## list of buyers who should take feedback
    pending_feedback_buyers_list = set(feedback_required_ids_from_erp)-set(buyers_already_took_feedback)

    # non_claimed_buyers = pending_feedback_buyers_list - claimed_buyers
    claimed_buyers = get_claimed_buyers()
    ## pending claimed_buyers_list - set from claimed_buyers
    claimed_buyers_list = []

    ## final list
    final_buyers_list = set(pending_feedback_buyers_list)-set(claimed_buyers_list)
    for buyer in final_buyers_list:
        vwrite(buyer)
    

def get_claimed_buyers():
    claimed_buyers = []
    params = {"Pagination":{"PageNumber":0}}
    claimed_buyers = get_request('GetUserDisputes', 'trading', params)
    vwrite("claimed_buyers")
    vwrite(claimed_buyers)
    return claimed_buyers

def get_feedback_required_ids_from_erp():
    feedback_required_ids_from_erp = []
    delivery_note_list = """
        select dn.posting_date,so.ebay_buyer_id from `tabDelivery Note Item` dni
        inner join `tabDelivery Note` dn on dn.name=dni.parent
        inner join `tabSales Order` so on so.name=dni.against_sales_order
        where dn.return_against is null and so.name like '%s' and dn.posting_date < '%s' and dn.posting_date > '%s' and dn.status='Completed'
        order by dn.creation desc
        """ % ("SO-Ebay-%",datetime.now() + timedelta(days=-5),datetime.now() + timedelta(days=-30))
    dns = []
    dns = frappe.db.sql(delivery_note_list, as_dict=1)
    for dn in dns:
        feedback_required_ids_from_erp.append(dn.get("ebay_buyer_id"))
    return feedback_required_ids_from_erp
    
