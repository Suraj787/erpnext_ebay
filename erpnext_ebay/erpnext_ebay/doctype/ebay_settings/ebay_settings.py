# -*- coding: utf-8 -*-
# Copyright (c) 2017, vwithv1602 and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from ebaysdk.finding import Connection
from ebaysdk.exception import ConnectionError

class EbaySettings(Document):
	def validate(self):
		# vwrite("inside it")
		if self.enable_ebay == 1:
			api = Connection(appid=self.app_id,
							 devid=self.dev_id,
							 certid=self.cert_id,
							 token=self.user_token,
							 config_file=None)
			try:
				response = api.execute('findItemsAdvanced', {
					'keywords': 'Hitachi-1-5-Ton-5-Star-Inverter-Split-Air-Conditioner-RAU518IWEA-Copper-White',
					'paginationInput': {
						'entriesPerPage': '25',
						'pageNumber': '1'
					},'sortOrder': 'CurrentPriceHighest'})
				frappe.msgprint(_("Ebay sync successful"))
			except ConnectionError as e:
				frappe.db.rollback()
				self.set("enable_ebay", 0)
				frappe.db.commit()
				frappe.msgprint(_("Invalid credentials. Ebay sync disabled"))

		else:
			frappe.msgprint(_("Ebay disabled"))

@frappe.whitelist()
def get_series():
		return {
			# "sales_order_series" : frappe.get_meta("Sales Order").get_options("naming_series") or "SO-Shopify-",
			# "sales_invoice_series" : frappe.get_meta("Sales Invoice").get_options("naming_series")  or "SI-Shopify-",
			# "delivery_note_series" : frappe.get_meta("Delivery Note").get_options("naming_series")  or "DN-Shopify-"
		}