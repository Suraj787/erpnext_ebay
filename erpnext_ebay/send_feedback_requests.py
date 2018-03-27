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

from pygapi.pygcontacts import get_contact_by_number,create_contact,update_contact,pre_queue_contact

@frappe.whitelist()
def send_ebay_feedback_request():
    feedback_required_ids_from_erp = get_feedback_required_ids_from_erp()
    ## buyers who already took feadback
    params = {"SoldList":{"Include":True,"OrderStatusFilter":"PaidAndShipped"}}
    myebayselling = get_request('GetMyeBaySelling', 'trading', params)
    buyer_took_feedback_result = myebayselling.get("SoldList").get("OrderTransactionArray").get("OrderTransaction")
    buyers_already_took_feedback = []
    for transaction in buyer_took_feedback_result:
        if transaction.get("Transaction").get("FeedbackReceived"):
            feedback_given_buyer = transaction.get("Transaction").get("Buyer").get("UserID")
            buyers_already_took_feedback.append(feedback_given_buyer)
            buyer_details = get_buyer_details(feedback_given_buyer)
            if buyer_details and buyer_details.get("phone"):
                createorupdatecontact(buyer_details,buyer_details.get("customer_name"))
    ## list of buyers who should take feedback
    pending_feedback_buyers_list = set(feedback_required_ids_from_erp)-set(buyers_already_took_feedback)
    ## pending claimed_buyers_list - set from claimed_buyers
    claimed_buyers_list = get_ebay_claimed_buyer_ids()
    ## final list
    final_buyers_list = set(pending_feedback_buyers_list)-set(claimed_buyers_list)
    for buyer in final_buyers_list:
        buyer_details = get_buyer_details(buyer)
        if buyer_details and buyer_details.get("phone"):
            createorupdatecontact(buyer_details,buyer_details.get("customer_name")+"_NF")
            

def get_buyer_details(buyerid):
    buyer_details = None
    fetch_mobile_query = """
    select  c.customer_name,a.phone,so.ebay_buyer_id,so.ebaytwo_buyer_id from `tabSales Order` so, `tabCustomer` c, `tabAddress` a where so.customer=c.name and a.address_title=c.name and so.ebay_buyer_id='%s' order by so.transaction_date limit 1
    """ % buyerid
    fetch_mobile_result = frappe.db.sql(fetch_mobile_query, as_dict=1)
    for row in fetch_mobile_result:
        buyer_details = row
    return buyer_details

def createorupdatecontact(buyer_details,name):
    mobile = buyer_details.get("phone")
    # >> Implementing pre queue google contacts
    # contactfromgoogle = get_contact_by_number(mobile)
    contactfromgoogle = None
    # << Implementing pre queue google contacts
    # >> Issue#21
    def get_prefix(name):
        second_index = name.replace('-', 'XXX', 1).find('-')-1
        filtered_name = name[second_index:len(name)]
        if filtered_name[-3:] == '_NF':
            actual_name = filtered_name[:-3]
        else:
            actual_name = filtered_name
        return name[:name.find(actual_name)]+actual_name
    # << Issue#21
    if contactfromgoogle:
        # >> Issue#21
        if contactfromgoogle.get("names")[0].get("displayName"):
            actual_name = get_prefix(contactfromgoogle.get("names")[0].get("displayName"))
        if name[-3:]=='_NF':
            name = actual_name+'_NF'
        else:
            name = actual_name
        # << Issue#21
        # update existing contact with google contact
        contact = {"name":name,"mobile":mobile}
        update_contact(contact)
        
    else:
        contact = {"name":name,"mobile":mobile}
        # >> Implementing pre queue google contacts
        # create_contact(contact)
        pre_queue_contact(contact)
        # << Implementing pre queue google contacts
        # create new google contact
    return ""

def get_feedback_required_ids_from_erp():
    feedback_required_ids_from_erp = []
    delivery_note_list = """
        select dn.posting_date,so.ebay_buyer_id from `tabDelivery Note Item` dni
        inner join `tabDelivery Note` dn on dn.name=dni.parent
        inner join `tabSales Order` so on so.name=dni.against_sales_order
        where dn.return_against is null and so.name like '%s' and dn.posting_date < '%s' and dn.posting_date > '%s' and dn.status='Completed'
        order by dn.creation desc
        """ % ("SO-Ebay-%",datetime.now() + timedelta(days=-10),datetime.now() + timedelta(days=-60))
    dns = []
    dns = frappe.db.sql(delivery_note_list, as_dict=1)
    for dn in dns:
        feedback_required_ids_from_erp.append(dn.get("ebay_buyer_id"))
    return feedback_required_ids_from_erp

def get_ebay_claimed_buyer_ids():
    ebay_claimed_buyer_ids = []
    delivery_note_list = """
        select * from `tabEbay Claims` where transaction_date > '%s'
        """ % str(datetime.now() + timedelta(days=-60))
    try:
        claims = frappe.db.sql(delivery_note_list, as_dict=1)
    except Exception, e:
        vwrite("Exception raised in get_ebay_claimed_buyer_ids")
        vwrite(e.message)
    
    for claim in claims:
        ebay_claimed_buyer_ids.append(claim.get("ebay_buyer_id"))
    return ebay_claimed_buyer_ids
