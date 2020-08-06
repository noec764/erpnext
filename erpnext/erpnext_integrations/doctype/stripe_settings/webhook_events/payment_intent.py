# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import flt

from .stripe import StripeWebhooksController

EVENT_MAP = {
	'payment_intent.created': 'update_payment_request',
	'payment_intent.canceled': 'update_payment_request',
	'payment_intent.payment_failed': 'update_payment_request',
	'payment_intent.processing': 'update_payment_request',
	'payment_intent.succeeded': 'create_submit_payment'
}

STATUS_MAP = {
	'payment_intent.created': 'Pending',
	'payment_intent.canceled': 'Failed',
	'payment_intent.payment_failed': 'Failed',
	'payment_intent.processing': 'Pending',
	'payment_intent.succeeded': 'Paid'
}

class StripePaymentIntentWebhookHandler(StripeWebhooksController):
	def __init__(self, **kwargs):
		super(StripePaymentIntentWebhookHandler, self).__init__(**kwargs)

		self.charges = []
		self.event_map = EVENT_MAP
		self.status_map = STATUS_MAP

		self.init_handler()
		self.handle_webhook()

	def get_charges(self):
		self.charges = [x.get("id") for x in self.data.get("data", {}).get("object", {}).get("charges", {}).get("data", [])]