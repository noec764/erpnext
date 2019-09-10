# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json

class GoCardlessWebhookHandler():
	def __init__(self, **kwargs):
		self.integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))
		self.data = json.loads(self.integration_request.get("data"))
		self.get_mandate()
		self.get_customer()
		self.get_subscription()

	def get_mandate(self):
		self.mandate = self.data.get("links", {}).get("mandate")

	def get_customer(self):
		self.gocardless_customer = self.data.get("links", {}).get("customer")

	def get_subscription(self):
		self.gocardless_subscription = self.data.get("links", {}).get("subscription")
