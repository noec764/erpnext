# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import nowdate

EVENT_MAP = {
	'invoice.created': 'create_invoice',
	'invoice.deleted': 'delete_invoice',
	'invoice.finalized': 'finalize_invoice',
	'invoice.payment_failed': 'fail_invoice',
	'invoice.payment_succeeded': 'pay_invoice',
	'invoice.voided': 'void_invoice'
}

class StripeInvoiceWebhookHandler():
	def __init__(self, **kwargs):
		self.integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))
		self.data = json.loads(self.integration_request.get("data"))
		self.invoice = None
		self.subscription = None

		if self.data.get("data", {}).get("object", {}).get("subscription"):
			self.get_linked_subscription()
			self.get_subscription_invoice()
		else:
			self.integration_request.db_set("error", _("This type of event is not handled by dokos"))
			self.integration_request.update_status({}, "Completed")

		self.handle_invoice_update()
		self.add_invoice_to_integration_request()

	def get_subscription_invoice(self):
		if self.subscription:
			self.subscription.flags.ignore_permissions = True
			self.subscription.process()
			self.invoice = self.subscription.get_current_invoice()
			if self.invoice:
				self.invoice.flags.ignore_permissions = True

	def get_linked_subscription(self):
		self.subscriptions = frappe.get_all("Subscription",\
			filters={"payment_gateway_reference": self.data.get("data", {}).get("object", {}).get("subscription")})

		if len(self.subscriptions) > 1:
			frappe.log_error(_("Several subscriptions are linked to Stripe subscription {0}").format(\
				self.data.get("data", {}).get("object", {}).get("subscription")), _("Stripe webhook action error"))
		elif len(self.subscriptions) == 0:
			frappe.log_error(_("Stripe subscription {0} is not linked to a subscription in dokos").format(\
				self.data.get("data", {}).get("object", {}).get("subscription")), _("Stripe webhook action error"))
		else:
			self.subscription = frappe.get_doc("Subscription", self.subscriptions[0].get("name"))

	def add_invoice_to_integration_request(self):
		self.integration_request.db_set("reference_doctype", "Sales Invoice")
		self.integration_request.db_set("reference_docname", self.invoice.name if self.invoice else None)

	def handle_invoice_update(self):
		target = EVENT_MAP.get(self.data.get("type"))
		if not target:
			self.integration_request.db_set("error", _("This type of event is not handled by dokos"))
			self.integration_request.update_status({}, "Completed")

		else:
			method = getattr(self, target)
			method()

	def create_invoice(self):
		try:
			if self.invoice:
				self.integration_request.db_set("error",\
					_("Subscription {0} has already invoice {1} for the current period").format(\
					self.subscription.name, self.invoice.name))
				self.integration_request.update_status({}, "Failed")
			else:
				self.subscription.process_active_subscription()
				self.invoice = self.subscription.get_current_invoice()
				self.integration_request.update_status({}, "Completed")
		except Exception as e:
			self.integration_request.db_set("error", e)
			self.integration_request.update_status({}, "Failed")

	def delete_invoice(self):
		try:
			self.invoice.cancel()
			self.integration_request.update_status({}, "Completed")
		except Exception as e:
			self.integration_request.db_set("error", e)
			self.integration_request.update_status({}, "Failed")

	def finalize_invoice(self):
		try:
			if self.invoice.docstatus == 0:
				self.invoice.submit()
			elif self.invoice.docstatus == 2:
				self.integration_request.db_set("error",\
					_("Sales invoice {0} is already cancelled").format(self.invoice.name))
				self.integration_request.update_status({}, "Completed")

			self.integration_request.update_status({}, "Completed")
		except Exception as e:
			self.integration_request.db_set("error", e)
			self.integration_request.update_status({}, "Failed")

	def fail_invoice(self):
		pass
		#TODO: Check if a payment has already been made for this invoice

	def pay_invoice(self):
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		try:
			pe = get_payment_entry("Sales Invoice", self.invoice.name)
			pe.reference_no = self.subscription.name
			pe.reference_date = nowdate()
			pe.flags.ignore_permissions = True
			pe.insert()
			pe.submit()
			self.integration_request.update_status({}, "Completed")
		except Exception as e:
			self.integration_request.db_set("error", e)
			self.integration_request.update_status({}, "Failed")

	def void_invoice(self):
		try:
			self.invoice.cancel()
			self.integration_request.update_status({}, "Completed")
		except Exception as e:
			self.integration_request.db_set("error", e)
			self.integration_request.update_status({}, "Failed")