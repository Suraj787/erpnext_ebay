from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .ebay_requests import post_request, get_request
from .utils import make_ebay_log
from vlog import vwrite

# def sync_customers():
# 	shopify_customer_list = []
# 	sync_shopify_customers(shopify_customer_list)
# 	frappe.local.form_dict.count_dict["customers"] = len(shopify_customer_list)
#
# 	sync_erpnext_customers(shopify_customer_list)
#
# def sync_shopify_customers(shopify_customer_list):
# 	for shopify_customer in get_shopify_customers():
# 		if not frappe.db.get_value("Customer", {"shopify_customer_id": shopify_customer.get('id')}, "name"):
# 			create_customer(shopify_customer, shopify_customer_list)

def create_customer(ebay_order, ebay_customer_list):
	vwrite('in create_customer')
	cust_id = ebay_order.get("BuyerUserID")
	cust_name = ebay_order.get("ShippingAddress").get("Name")

	try:
		customer = frappe.get_doc({
			"doctype": "Customer",
			"name": cust_id,
			"customer_name" : cust_name,
			"ebay_customer_id": cust_id,
			# "sync_with_shopify": 1,
			# "customer_group": ebay_settings.customer_group,
			# "territory": frappe.utils.nestedset.get_root_of("Territory"),
			"customer_type": _("Individual")
		})
		customer.flags.ignore_mandatory = True
		test = customer.insert()
		vwrite(test)
		if customer:
			create_customer_address(ebay_order, cust_id)
	
		ebay_customer_list.append(ebay_order.get("BuyerUserID"))
		frappe.db.commit()
			
	except Exception, e:
		if e.args[0] and e.args[0].startswith("402"):
			raise e
		else:
			make_ebay_log(title=e.message, status="Error", method="create_customer", message=frappe.get_traceback(),
				request_data=ebay_order, exception=True)
		
def create_customer_address(ebay_order, ebay_customer):
	vwrite('in create_customer_address')
	test = {
			"doctype": "Address",
			"ebay_address_id": ebay_order.get("ShippingAddress").get("AddressID"),
			"address_title": ebay_order.get("ShippingAddress").get("Name"),
			"address_type": "",
			"address_line1": ebay_order.get("ShippingAddress").get("Street1"),
			"address_line2": ebay_order.get("ShippingAddress").get("Street2"),
			"city": ebay_order.get("ShippingAddress").get("CityName"),
			"state": ebay_order.get("ShippingAddress").get("PB"),
			"pincode": ebay_order.get("ShippingAddress").get("PostalCode"),
			"country": ebay_order.get("ShippingAddress").get("Country"),
			"phone": ebay_order.get("ShippingAddress").get("Phone"),
			"email_id": ebay_order.get("TransactionArray").get("Transaction")[0].get("Buyer").get("Email"),
			"links": [{
				"link_doctype": "Customer",
				# "link_name": ebay_order.get("BuyerUserID")
				"link_name": ebay_order.get("ShippingAddress").get("Name")
			}]
		}
	vwrite(test)
	try :
		if not frappe.db.get_value("Address", {"ebay_address_id": ebay_order.get("ShippingAddress").get("AddressID")}, "name"):
			frappe.get_doc({
				"doctype": "Address",
				"ebay_address_id": ebay_order.get("ShippingAddress").get("AddressID"),
				"address_title": ebay_order.get("ShippingAddress").get("Name"),
				"address_type": "Shipping",
				"address_line1": ebay_order.get("ShippingAddress").get("Street1"),
				"address_line2": ebay_order.get("ShippingAddress").get("Street2"),
				"city": ebay_order.get("ShippingAddress").get("CityName"),
				"state": ebay_order.get("ShippingAddress").get("PB"),
				"pincode": ebay_order.get("ShippingAddress").get("PostalCode"),
				# "country": ebay_order.get("ShippingAddress").get("Country"),
				"country": None,
				"phone": ebay_order.get("ShippingAddress").get("Phone"),
				"email_id": ebay_order.get("TransactionArray").get("Transaction")[0].get("Buyer").get("Email"),
				"links": [{
					"link_doctype": "Customer",
					# "link_name": ebay_order.get("BuyerUserID")
					"link_name": ebay_order.get("ShippingAddress").get("Name")
				}]
			}).insert()
		else:
			frappe.get_doc({
				"doctype": "Address",
				"ebay_address_id": ebay_order.get("ShippingAddress").get("AddressID"),
				"address_title": ebay_order.get("ShippingAddress").get("Name"),
				"address_type": "Shipping",
				"address_line1": ebay_order.get("ShippingAddress").get("Street1"),
				"address_line2": ebay_order.get("ShippingAddress").get("Street2"),
				"city": ebay_order.get("ShippingAddress").get("CityName"),
				"state": ebay_order.get("ShippingAddress").get("PB"),
				"pincode": ebay_order.get("ShippingAddress").get("PostalCode"),
				# "country": ebay_order.get("ShippingAddress").get("Country"),
				"country": None,
				"phone": ebay_order.get("ShippingAddress").get("Phone"),
				"email_id": ebay_order.get("TransactionArray").get("Transaction")[0].get("Buyer").get("Email"),
				"links": [{
					"link_doctype": "Customer",
					# "link_name": ebay_order.get("BuyerUserID")
					"link_name": ebay_order.get("ShippingAddress").get("Name")
				}]
			}).save()

	except Exception, e:
		vwrite('exception occurred')
		make_ebay_log(title=e.message, status="Error", method="create_customer_address", message=frappe.get_traceback(),
			request_data=ebay_customer, exception=True)


def get_address_title_and_type(customer_name, index):
	address_type = _("Billing")
	address_title = customer_name
	if frappe.db.get_value("Address", "{0}-{1}".format(customer_name.strip(), address_type)):
		address_title = "{0}-{1}".format(customer_name.strip(), index)
		
	return address_title, address_type 
	
def sync_erpnext_customers(shopify_customer_list):
	shopify_settings = frappe.get_doc("Shopify Settings", "Shopify Settings")
	
	condition = ["sync_with_shopify = 1"]
	
	last_sync_condition = ""
	if shopify_settings.last_sync_datetime:
		last_sync_condition = "modified >= '{0}' ".format(shopify_settings.last_sync_datetime)
		condition.append(last_sync_condition)
	
	customer_query = """select name, customer_name, shopify_customer_id from tabCustomer 
		where {0}""".format(" and ".join(condition))
		
	for customer in frappe.db.sql(customer_query, as_dict=1):
		try:
			if not customer.shopify_customer_id:
				create_customer_to_shopify(customer)
			
			else:
				if customer.shopify_customer_id not in shopify_customer_list:
					update_customer_to_shopify(customer, shopify_settings.last_sync_datetime)
			
			frappe.local.form_dict.count_dict["customers"] += 1
			frappe.db.commit()
		except Exception, e:
			make_ebay_log(title=e.message, status="Error", method="sync_erpnext_customers", message=frappe.get_traceback(),
				request_data=customer, exception=True)

def create_customer_to_shopify(customer):
	shopify_customer = {
		"first_name": customer['customer_name'],
	}
	
	shopify_customer = post_request("/admin/customers.json", { "customer": shopify_customer})
	
	customer = frappe.get_doc("Customer", customer['name'])
	customer.shopify_customer_id = shopify_customer['customer'].get("id")
	
	customer.flags.ignore_mandatory = True
	customer.save()
	
	addresses = get_customer_addresses(customer.as_dict())
	for address in addresses:
		sync_customer_address(customer, address)

def sync_customer_address(customer, address):
	address_name = address.pop("name")

	shopify_address = post_request("/admin/customers/{0}/addresses.json".format(customer.shopify_customer_id),
	{"address": address})
		
	address = frappe.get_doc("Address", address_name)
	address.shopify_address_id = shopify_address['customer_address'].get("id")
	address.save()
	
def update_customer_to_shopify(customer, last_sync_datetime):
	shopify_customer = {
		"first_name": customer['customer_name'],
		"last_name": ""
	}
	
	try:
		put_request("/admin/customers/{0}.json".format(customer.shopify_customer_id),\
			{ "customer": shopify_customer})
		update_address_details(customer, last_sync_datetime)
		
	except requests.exceptions.HTTPError, e:
		if e.args[0] and e.args[0].startswith("404"):
			customer = frappe.get_doc("Customer", customer.name)
			customer.shopify_customer_id = ""
			customer.sync_with_shopify = 0
			customer.flags.ignore_mandatory = True
			customer.save()
		else:
			raise
			
def update_address_details(customer, last_sync_datetime):
	customer_addresses = get_customer_addresses(customer, last_sync_datetime)
	for address in customer_addresses:
		if address.shopify_address_id:
			url = "/admin/customers/{0}/addresses/{1}.json".format(customer.shopify_customer_id,\
			address.shopify_address_id)
			
			address["id"] = address["shopify_address_id"]
			
			del address["shopify_address_id"]
			
			put_request(url, { "address": address})
			
		else:
			sync_customer_address(customer, address)
			
def get_customer_addresses(customer, last_sync_datetime=None):
	conditions = ["dl.parent = addr.name", "dl.link_doctype = 'Customer'",
		"dl.link_name = '{0}'".format(customer['name'])]
	
	if last_sync_datetime:
		last_sync_condition = "addr.modified >= '{0}'".format(last_sync_datetime)
		conditions.append(last_sync_condition)
	
	address_query = """select addr.name, addr.address_line1 as address1, addr.address_line2 as address2,
		addr.city as city, addr.state as province, addr.country as country, addr.pincode as zip,
		addr.shopify_address_id from tabAddress addr, `tabDynamic Link` dl
		where {0}""".format(' and '.join(conditions))
			
	return frappe.db.sql(address_query, as_dict=1)