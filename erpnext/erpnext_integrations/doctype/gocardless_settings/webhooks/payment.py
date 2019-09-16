# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from erpnext.erpnext_integrations.doctype.gocardless_settings.webhooks.utils import GoCardlessWebhookHandler

EVENT_MAP = {
	'created': 'create_invoice',
	'customer_approval_granted': 'pay_invoice',
	'customer_approval_denied': 'change_status',
	'submitted': 'create_invoice',
	'confirmed': 'pay_invoice',
	'cancelled': 'cancel_invoice',
	'failed': 'fail_invoice',
	'charged_back': 'create_credit_note',
	'chargeback_cancelled': 'cancel_credit_note',
	'paid_out': 'reconcile_payment',
	'late_failure_settled': 'change_status',
	'chargeback_settled': 'change_status',
	'resubmission_requested': 'change_status'
}

class GoCardlessPaymentWebhookHandler(GoCardlessWebhookHandler):
	def __init__(self, **kwargs):
		super(GoCardlessPaymentWebhookHandler, self).__init__(**kwargs)

		if self.gocardless_subscription:
			self.get_subscription_invoice()
		else:
			self.integration_request.db_set("error", _("This type of event is not handled by dokos"))
			self.integration_request.update_status({}, "Completed")

		self.handle_invoice_update()
		self.add_invoice_to_integration_request()

	def get_linked_subscription(self):
		self.subscriptions = frappe.get_all("Subscription",\
			filters={"payment_gateway_reference": self.subscription})

		if len(self.subscriptions) > 1:
			frappe.log_error(_("Several subscriptions are linked to GoCardless subscription {0}").format(\
				self.gocardless_subscription), _("GoCardless webhook action error"))
		elif len(self.subscriptions) == 0:
			frappe.log_error(_("GoCardless subscription {0} is not linked to a subscription in dokos").format(\
				self.gocardless_subscription), _("GoCardless webhook action error"))
		else:
			self.subscription = frappe.get_doc("Subscription", self.subscriptions[0].get("name"))

	def get_subscription_invoice(self):
		if self.subscription:
			self.subscription.flags.ignore_permissions = True
			self.subscription.process()
			self.invoice = self.subscription.get_current_invoice()
			if self.invoice:
				self.invoice.flags.ignore_permissions = True

	def handle_invoice_update(self):
		target = target = EVENT_MAP.get(self.data.get("action"))
		if not target:
			self.integration_request.db_set("error", _("This type of event is not handled by dokos"))
			self.integration_request.update_status({}, "Completed")
		else:
			method = getattr(self, target)
			method()

	def add_invoice_to_integration_request(self):
		self.integration_request.db_set("reference_doctype", "Sales Invoice")
		self.integration_request.db_set("reference_docname", self.invoice.name if self.invoice else None)

	#TODO: Commmonify with Stripe
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
		self.cancel_invoice()

	def cancel_invoice(self):
		try:
			self.invoice.cancel()
			self.integration_request.update_status({}, "Completed")
		except Exception as e:
			self.integration_request.db_set("error", e)
			self.integration_request.update_status({}, "Failed")

	def pay_invoice(self):
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

	#TODO: Add missing methods
	def fail_invoice(self):
		pass

	def create_credit_note(self):
		pass

	def cancel_credit_note(self):
		pass

	def reconcile_payment(self):
		pass

	def change_status(self):
		pass