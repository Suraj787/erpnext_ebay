from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import datetime,timedelta

from pygapi.pygcontacts import get_contact_by_number,create_contact,update_contact
from erpnext_ebay.vlog import vwrite

def findnth(haystack, needle, n):
    return haystack.replace(needle, 'XXX', 1).find(needle)-1
def get_actual_name(existing_name_raw):
    existing_name_arr = existing_name_raw.split('-')
    if (len(existing_name_arr)>1) and (existing_name_arr[0].lower()=='hot' or existing_name_arr[0].lower()=='warm' or existing_name_arr[0].lower().replace(" ","")=='notinterested'):
        return existing_name_raw[findnth(existing_name_raw,'-',2):len(existing_name_raw)]
    else:
        return existing_name_raw
def lead_status_modifier():
    # get all `Hot` leads (hot_leads_older_than_two_days) which are older than 2 days
    hot_leads_query = """
    select name,lead_name,mobile_no,interested_in from `tabLead` where status='Hot' and modified < NOW() - INTERVAL 2 DAY
    """
    hot_leads = frappe.db.sql(hot_leads_query, as_dict=1)
    # convert `status` of hot_leads_older_than_two_days to `Warm`
    for hot_lead in hot_leads:
        frappe.db.sql(
            """update tabLead set status='%s', modified='%s' where name='%s'""" %("Warm",datetime.now(),hot_lead.get("name"))
        )
        frappe.db.commit()
        result = get_contact_by_number(hot_lead.get("mobile_no"))
        if result:
            # contact_name_format: <status>-<interestedIn>-<customer_name><_NF/{empty}> | eg: Hot-Laptop-John_NF/ Warm-Mobile-John
            existing_name_raw = result.get("names")[0].get("displayName")
            actual_name = get_actual_name(existing_name_raw)
            if(actual_name[:5]=='LEAD-'):
                actual_name = hot_lead.get("lead_name")
            contact_name = "warm-"+hot_lead.get("interested_in")+'-'+actual_name
            contact = {"name":contact_name,"mobile":hot_lead.get("mobile_no")}
            update_contact(contact)
        else:
            contact_name = "warm-"+hot_lead.get("interested_in")+'-'+hot_lead.get("lead_name")
            contact = {"name":contact_name,"mobile":hot_lead.get("mobile_no")}
            create_contact(contact)
    
    # get all `Warm` leads (warm_leads_older_than_three_days) which are older than 3 days
    warm_leads_query = """
    select name,lead_name,mobile_no,interested_in from `tabLead` where status='Warm' and modified < NOW() - INTERVAL 3 DAY
    """
    warm_leads = frappe.db.sql(warm_leads_query, as_dict=1)
    # convert `status` of warm_leads_older_than_three_days to `Not Interested`
    for warm_lead in warm_leads:
        frappe.db.sql(
            """update tabLead set status='%s', modified='%s' where name='%s'""" %("Not Interested",datetime.now(),warm_lead.get("name"))
        )
        frappe.db.commit()
        result = get_contact_by_number(warm_lead.get("mobile_no"))
        if result:
            # contact_name_format: <status>-<interestedIn>-<customer_name><_NF/{empty}> | eg: Hot-Laptop-John_NF/ Warm-Mobile-John
            existing_name_raw = result.get("names")[0].get("displayName")
            actual_name = get_actual_name(existing_name_raw)
            if(actual_name[:5]=='LEAD-'):
                actual_name = warm_lead.get("lead_name")
            contact_name = "notinterested-"+warm_lead.get("interested_in")+'-'+actual_name
            contact = {"name":contact_name,"mobile":warm_lead.get("mobile_no")}
            update_contact(contact)
        else:
            contact_name = "notinterested-"+warm_lead.get("interested_in")+'-'+warm_lead.get("lead_name")
            contact = {"name":contact_name,"mobile":warm_lead.get("mobile_no")}
            create_contact(contact)

