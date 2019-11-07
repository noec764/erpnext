# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import flt

from erpnext.erpnext_integrations.doctype.gocardless_settings.webhooks_documents.utils import GoCardlessWebhookHandler

EVENT_MAP = {
	'created': 'create_invoice',
	'customer_approval_granted': 'create_and_pay_invoice',
	'customer_approval_denied': 'change_status',
	'submitted': 'submit_invoice',
	'confirmed': 'create_and_pay_invoice',
	'cancelled': 'cancel_invoice',
	'failed': 'fail_invoice',
	'charged_back': 'create_credit_note',
	'chargeback_cancelled': 'cancel_credit_note',
	'paid_out': 'submit_payment',
	'late_failure_settled': 'change_status',
	'chargeback_settled': 'change_status',
	'resubmission_requested': 'change_status'
}

class GoCardlessPaymentWebhookHandler(GoCardlessWebhookHandler):
	def __init__(self, **kwargs):
		super(GoCardlessPaymentWebhookHandler, self).__init__(**kwargs)

		self.event_map = EVENT_MAP
		self.payment_gateway = frappe.db.get_value("Payment Gateway",\
			dict(gateway_settings="GoCardless Settings", gateway_controller=self.integration_request.get("payment_gateway_controller")))

		if self.gocardless_subscription:
			self.get_linked_subscription()
			self.get_subscription_invoice()
		elif self.gocardless_payment:
			self.get_one_off_invoice()

		if self.gocardless_payment:
			self.integration_request.db_set("service_id", self.gocardless_payment)
			self.integration_request.load_from_db()

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

	def create_and_pay_invoice(self):
		if self.invoice.docstatus == 0:
			self.submit_invoice()

		self.pay_invoice()

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
			frappe.log_error(frappe.get_traceback(), _("GoCardless invoice submission error"))
			self.set_as_failed(e)

	def add_fees_before_submission(self):
		self.get_payout()
		if self.gocardless_payout:
			payout_items = self.gocardless_settings.get_payout_items_list({"payout": self.gocardless_payout})

			output = ""
			for p in payout_items:
				output += str(p.__dict__)
			self.integration_request.db_set("output", output)

			self.base_amount = self.gocardless_settings.get_base_amount(payout_items)
			self.fee_amount = self.gocardless_settings.get_fee_amount(payout_items)
			#TODO: Handle exchange rates
			# self.exchange_rate = self.gocardless_settings.get_exchange_rate(payout)

			#TODO: Commonify with payment request
			gateway_defaults = frappe.db.get_value("Payment Gateway", self.payment_gateway,\
				["fee_account", "cost_center", "mode_of_payment"], as_dict=1) or dict()

			#TODO: Handle exchange rates
			# if self.exchange_rate:
			#	self.payment_entry.update({
			#		"target_exchange_rate": self.exchange_rate,
			#	})

			if self.fee_amount and gateway_defaults.get("fee_account") and gateway_defaults.get("cost_center"):
				fees = flt(self.fee_amount) * flt(self.payment_entry.get("target_exchange_rate", 1))
				self.payment_entry.update({
					"paid_amount": flt(self.base_amount or self.payment_entry.paid_amount) + fees,
					"received_amount": flt(self.payment_entry.received_amount) + fees
				})

				self.payment_entry.append("deductions", {
					"account": gateway_defaults.get("fee_account"),
					"cost_center": gateway_defaults.get("cost_center"),
					"amount": self.fee_amount
				})

				self.payment_entry.set_amounts()
