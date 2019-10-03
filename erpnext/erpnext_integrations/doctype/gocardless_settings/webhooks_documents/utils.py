# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json

from erpnext.erpnext_integrations.webhooks_controller import WebhooksController

class GoCardlessWebhookHandler(WebhooksController):
	def __init__(self, **kwargs):
		super(GoCardlessWebhookHandler, self).__init__(**kwargs)

		self.get_mandate()
		self.get_customer()
		self.get_subscription()

	def get_mandate(self):
		self.mandate = self.data.get("links", {}).get("mandate")

	def get_customer(self):
		self.gocardless_customer = self.data.get("links", {}).get("customer")

	def get_subscription(self):
		self.gocardless_subscription = self.data.get("links", {}).get("subscription")

	def get_payment(self):
		self.gocardless_payment = self.data.get("links", {}).get("payment")
