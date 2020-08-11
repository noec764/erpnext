# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import flt

from erpnext.erpnext_integrations.webhooks_controller import WebhooksController
from erpnext.erpnext_integrations.doctype.stripe_settings.api import StripeCharge

class StripeWebhooksController(WebhooksController):
	def __init__(self, **kwargs):
		super(StripeWebhooksController, self).__init__(**kwargs)
		self.status_map = {}
		self.period_start = None
		self.period_end = None

	def init_handler(self):
		self.stripe_settings = frappe.get_doc("Stripe Settings", self.integration_request.get("payment_gateway_controller"))
		self.payment_gateway = frappe.get_doc("Payment Gateway", dict(
			gateway_settings="Stripe Settings",
			gateway_controller=self.integration_request.get("payment_gateway_controller")
			)
		)

		self.get_metadata()
		if self.metadata:
			self.get_payment_request()

	def handle_webhook(self):
		self.action_type = self.data.get("type")

		if self.metadata:
			self.handle_update()
		else:
			self.set_as_failed(_("No metadata found in this webhook"))

	def get_metadata(self):
		self.metadata = self.data.get("data", {}).get("object", {}).get("metadata")

	def get_payment_request(self):
		payment_request_id = None

		if self.metadata.get("reference_doctype") == "Subscription":
			self.subscription = frappe.get_doc("Subscription", self.metadata.get("reference_name"))
			self.period_start = getdate(datetime.datetime.utcfromtimestamp(self.data.get("data", {}).get("object", {}).get("period_start")))
			self.period_end = getdate(datetime.datetime.utcfromtimestamp(self.data.get("data", {}).get("object", {}).get("period_end")))
			if self.period_start and self.period_end:
				payment_request_id = self.subscription.get_payment_request_for_period(self.period_start, self.period_end)

		elif self.metadata.get("payment_request"):
			payment_request_id = self.metadata.get("payment_request")
		elif self.metadata.get("reference_doctype") == "Payment Request":
			payment_request_id = self.metadata.get("reference_name")

		self.payment_request = frappe.get_doc("Payment Request", payment_request_id)

	def update_payment_request(self):
		if self.payment_request and self.payment_request.status not in (self.status_map.get(self.action_type), 'Paid', 'Completed'):
			frappe.db.set_value(self.payment_request.doctype, self.payment_request.name, 'status', self.status_map.get(self.action_type))
			self.set_as_completed()

	def add_fees_before_submission(self, payment_entry):
		output = []
		base_amount = exchange_rate = fee_amount = 0.0
		for charge in self.charges:
			stripe_charge = StripeCharge(self.stripe_settings).retrieve(charge)
			output.append(stripe_charge)

			base_amount += flt(stripe_charge.balance_transaction.get("amount")) / 100
			fee_amount += flt(stripe_charge.balance_transaction.get("fee")) / 100

			# We suppose all charges within the same payment intent have the same exchange rate
			exchange_rate = (1 / flt(stripe_charge.balance_transaction.get("exchange_rate"))) or 1

			payment_entry.mode_of_payment = self.payment_gateway.mode_of_payment

			if exchange_rate:
				payment_entry.update({
					"target_exchange_rate": exchange_rate,
				})

			if fee_amount and self.payment_gateway.fee_account and self.payment_gateway.cost_center:
				fees = fee_amount * exchange_rate
				payment_entry.update({
					"paid_amount": flt(base_amount or payment_entry.paid_amount) - fees,
					"received_amount": flt(base_amount or payment_entry.received_amount) - fees
				})

				payment_entry.append("deductions", {
					"account": self.payment_gateway.fee_account,
					"cost_center": self.payment_gateway.cost_center,
					"amount": fee_amount
				})

				payment_entry.set_amounts()

		self.integration_request.db_set("output", json.dumps(output, indent=4))

	def create_submit_payment(self):
		self.get_charges()
		if self.charges:
			for charge in self.charges:
				self.create_payment(charge)
				self.submit_payment(charge)

		self.update_payment_request()