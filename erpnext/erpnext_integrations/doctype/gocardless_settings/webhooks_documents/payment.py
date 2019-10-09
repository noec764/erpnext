# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from erpnext.erpnext_integrations.doctype.gocardless_settings.webhooks_documents.utils import GoCardlessWebhookHandler

EVENT_MAP = {
	'created': 'create_invoice',
	'customer_approval_granted': 'pay_invoice',
	'customer_approval_denied': 'change_status',
	'submitted': 'submit_invoice',
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

		self.event_map = EVENT_MAP

		if self.gocardless_subscription:
			self.get_linked_subscription()
			self.get_subscription_invoice()
		else:
			self.get_payment()
			if self.gocardless_payment:
				self.get_one_off_invoice()

		if self.data.get("links", {}).get("payment"):
			self.integration_request.db_set("service_id", self.data.get("links", {}).get("payment"))

		self.action_type = self.data.get("action")
		self.handle_invoice_update()
		self.add_reference_to_integration_request()

	def get_linked_subscription(self):
		self.subscriptions = frappe.get_all("Subscription", filters={"payment_gateway_reference": self.gocardless_subscription})

		if len(self.subscriptions) > 1:
			frappe.log_error(_("Several subscriptions are linked to GoCardless subscription {0}").format(\
				self.gocardless_subscription), _("GoCardless webhook action error"))
		elif len(self.subscriptions) == 0:
			frappe.log_error(_("GoCardless subscription {0} is not linked to a subscription in dokos").format(\
				self.gocardless_subscription), _("GoCardless webhook action error"))
		else:
			self.subscription = frappe.get_doc("Subscription", self.subscriptions[0].get("name"))

	# TODO: Add some amount checks before submit
	def submit_invoice(self):
		try:
			if self.invoice:
				if self.invoice.docstatus == 0:
					self.invoice.submit()
				elif self.invoice.docstatus == 2:
					self.integration_request.db_set("error",\
						_("Sales invoice {0} is already cancelled").format(self.invoice.name))
					self.integration_request.update_status({}, "Completed")

				self.integration_request.update_status({}, "Completed")
			else:
				self.set_as_failed(_("The corresponding invoice could not be found"))
		except Exception as e:
			self.set_as_failed(e)
