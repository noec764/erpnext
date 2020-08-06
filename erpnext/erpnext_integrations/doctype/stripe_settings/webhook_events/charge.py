# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import flt

from .stripe import StripeWebhooksController

EVENT_MAP = {
	'charge.captured': 'create_payment',
	'charge.expired': 'cancel_payment',
	'charge.failed': 'cancel_payment',
	'charge.pending': 'create_payment',
	'charge.succeeded': 'submit_stripe_payment'
}

class StripeChargeWebhookHandler(StripeWebhooksController):
	def __init__(self, **kwargs):
		super(StripeChargeWebhookHandler, self).__init__(**kwargs)

		self.set_as_failed(_("The Charge Webhook is no longer supported. Please add Payment Intent to your webhooks instead."))

	def init_handler(self):
		self.stripe_settings = frappe.get_doc("Stripe Settings", self.integration_request.get("payment_gateway_controller"))
		self.payment_gateway = frappe.db.get_value("Payment Gateway",\
			dict(gateway_settings="Stripe Settings", gateway_controller=self.integration_request.get("payment_gateway_controller")))

		self.get_charge()
		self.get_invoice()
		self.get_metadata()

	def get_charge(self):
		charge_id = self.data.get("data", {}).get("object", {}).get("id")
		self.charge = self.stripe_settings.get_charge_on_stripe(charge_id)

	def get_invoice(self):
		self.stripe_invoice = self.stripe_settings.stripe.Invoice.retrieve(
			self.charge.get("invoice")
		)

	def get_metadata(self):
		self.metadata = getattr(self.charge, "metadata")

		if not self.metadata:
			self.stripe_subscription = self.stripe_settings.stripe.Subscription.retrieve(
				self.stripe_invoice.get("subscription")
			)
			self.metadata = getattr(self.stripe_subscription, "metadata")

	def submit_stripe_payment(self):
		if len(frappe.get_all("Integration Request", filters={"service_id": self.integration_request.get("service_id")})) == 1:
			self.create_payment()
			self.submit_payment()
		else:
			self.submit_payment()
