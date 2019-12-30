# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import getdate, formatdate, nowdate

from erpnext.erpnext_integrations.webhooks_controller import WebhooksController

class GoCardlessWebhookHandler(WebhooksController):
	def __init__(self, **kwargs):
		super(GoCardlessWebhookHandler, self).__init__(**kwargs)

		self.gocardless_settings = frappe.get_doc("GoCardless Settings", \
			self.integration_request.get("payment_gateway_controller"))
		self.get_mandate()
		self.get_customer()
		self.get_payment()
		self.get_reference_date()
		self.get_subscription()

	def get_mandate(self):
		self.mandate = self.data.get("links", {}).get("mandate")

	def get_customer(self):
		self.gocardless_customer = self.data.get("links", {}).get("customer")

	def get_subscription(self):
		self.gocardless_subscription = self.data.get("links", {}).get("subscription")

		if not self.gocardless_subscription and self.gocardless_payment:
			payment = self.gocardless_settings.get_payment_by_id(self.gocardless_payment)
			if payment:
				self.gocardless_subscription = payment.attributes.get("links", {}).get("subscription")

	def get_payment(self):
		self.gocardless_payment = self.data.get("links", {}).get("payment")

	def get_reference_date(self):
		self.reference_date = getdate(getattr(self.get_payment_document(), "charge_date"))

	def get_payment_document(self):
		return self.gocardless_settings.get_payments_on_gocardless(id=self.gocardless_payment) if self.gocardless_payment else {}

	def get_payout(self):
		self.gocardless_payout = self.data.get("links", {}).get("payout")

	def check_subscription_dates(self):
		if self.subscription and self.gocardless_payment:
			payment = self.gocardless_settings.get_payment_by_id(self.gocardless_payment)

			charge_date = payment.attributes.get("charge_date")

			if getdate(charge_date) > getdate(self.subscription.current_invoice_end) \
				and getdate(self.subscription.current_invoice_end) >= getdate(nowdate()):
				self.integration_request.db_set("error", _("This event will be processed after the {}").format(\
					formatdate(self.subscription.current_invoice_end)))
				self.integration_request.update_status({}, "Queued")
			else:
				self.integration_request.update_status({}, "Pending")
