# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from erpnext.erpnext_integrations.webhooks_controller import WebhooksController

EVENT_MAP = {
	'invoice.created': 'create_invoice',
	'invoice.deleted': 'delete_invoice',
	'invoice.finalized': 'finalize_invoice',
	'invoice.payment_failed': 'fail_invoice',
	'invoice.payment_succeeded': 'pay_invoice',
	'invoice.voided': 'void_invoice'
}

class StripeInvoiceWebhookHandler(WebhooksController):
	def __init__(self, **kwargs):
		super(StripeInvoiceWebhookHandler, self).__init__(**kwargs)

		self.event_map = EVENT_MAP

		self.stripe_settings = frappe.get_doc("Stripe Settings", self.integration_request.get("payment_gateway_controller"))
		self.payment_gateway = frappe.db.get_value("Payment Gateway",\
			dict(gateway_settings="Stripe Settings", gateway_controller=self.integration_request.get("payment_gateway_controller")))

		if self.data.get("data", {}).get("object", {}).get("subscription"):
			self.get_linked_subscription()
			self.get_subscription_invoice()
		else:
			self.integration_request.db_set("error", _("This type of event is not handled by dokos"))
			self.integration_request.update_status({}, "Completed")

		self.handle_invoice_update()
		self.add_reference_to_integration_request()

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

	def finalize_invoice(self):
		try:
			if self.invoice:
				if self.invoice.docstatus == 0:
					self.check_and_finalize_invoice()
				elif self.invoice.docstatus == 2:
					self.integration_request.db_set("error",\
						_("Sales invoice {0} is already cancelled").format(self.invoice.name))
					self.integration_request.update_status({}, "Completed")

				self.integration_request.update_status({}, "Completed")
			else:
				self.set_as_failed(_("The corresponding invoice could not be found"))
		except Exception as e:
			self.set_as_failed(e)

	def void_invoice(self):
		try:
			self.invoice.cancel()
			self.integration_request.update_status({}, "Completed")
		except Exception as e:
			self.integration_request.db_set("error", str(e))
			self.integration_request.update_status({}, "Failed")

	def check_and_finalize_invoice(self):
		submit = self.check_total_amount()
		if submit:
			self.invoice.submit()

	def check_total_amount(self):
		if (self.invoice.grand_total * 100) == self.data.get("data", {}).get("object", {}).get("amount_due"):
			return True
		else:
			self.set_as_failed(_("The total amount in this document and in the sales invoice don't match"))
			return False
