from __future__ import unicode_literals
import frappe

class EbayError(frappe.ValidationError): pass
class EbaySetupError(frappe.ValidationError): pass