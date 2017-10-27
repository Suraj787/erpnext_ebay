from __future__ import unicode_literals
import frappe
import json
from vlog import ebaydebug

def disable_ebay_sync_for_item(item, rollback=False):
    """Disable Item if not exist on ebay"""
    if rollback:
        frappe.db.rollback()

    item.sync_with_ebay = 0
    item.sync_qty_with_ebay = 0
    item.save(ignore_permissions=True)
    frappe.db.commit()

def disable_ebay_sync_on_exception():
	frappe.db.rollback()
	frappe.db.set_value("Ebay Settings", None, "enable_ebay", 0)
	frappe.db.commit()


def make_ebay_log(title="Sync Log", status="Queued", method="sync_ebay", message=None, exception=False,
                     name=None, request_data={}):
    # ebaydebug("DEBUG START ==>")
    # ebaydebug("title: %s, status: %s, method: %s, message: %s, exception: %s, name: %s, request_data: %s" %(title, status, method, message, exception,name, request_data))
    make_log_flag = True
    # log_message = message if message else frappe.get_traceback()
    # log_query = """select name from `tabEbay Log` where title = '%s' and message='%s' and method='%s' and status='%s' and request_data='%s'""" %(title[0:140],log_message,method,status,json.dumps(request_data))
    log_query = """select name from `tabEbay Log` where title = '%s' and method='%s' and request_data='%s'""" % (
    title[0:140].replace("'","''"), method, json.dumps(request_data))
    # ebaydebug(log_query)
    if status!="Queued" and title!="Sync Completed":
        if len(frappe.db.sql(log_query, as_dict=1)) > 0:
            make_log_flag = False
    if make_log_flag:
        if not name:
            name = frappe.db.get_value("Ebay Log", {"status": "Queued"})

            if name:
                """ if name not provided by log calling method then fetch existing queued state log"""
                log = frappe.get_doc("Ebay Log", name)

            else:
                """ if queued job is not found create a new one."""
                log = frappe.get_doc({"doctype": "Ebay Log"}).insert(ignore_permissions=True)

            if exception:
                frappe.db.rollback()
                log = frappe.get_doc({"doctype": "Ebay Log"}).insert(ignore_permissions=True)

            log.message = message if message else frappe.get_traceback()
            log.title = title[0:140]
            log.method = method
            log.status = status
            log.request_data = json.dumps(request_data)

            log.save(ignore_permissions=True)
            frappe.db.commit()
    # ebaydebug("DEBUG END <==")
