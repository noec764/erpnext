# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import flt

from .stripe import StripeWebhooksController

EVENT_MAP = {
	'invoice.created': 'get_or_create_invoice',
	'invoice.deleted': 'update_payment_request',
	'invoice.finalized': 'update_payment_request',
	'invoice.marked_uncollectible': 'update_payment_request',
	'invoice.paid': 'update_payment_request',
	'invoice.payment_action_required': 'update_payment_request',
	'invoice.payment_failed': 'update_payment_request',
	'invoice.payment_succeeded': 'update_payment_request',
	'invoice.sent': 'update_payment_request',
	'invoice.upcoming': 'update_payment_request',
	'invoice.updated': 'update_payment_request',
	'invoice.voided': 'update_payment_request'
}

class StripeInvoiceWebhookHandler(StripeWebhooksController):
	def __init__(self, **kwargs):
		super(StripeInvoiceWebhookHandler, self).__init__(**kwargs)
		self.event_map = EVENT_MAP

		self.init_handler()
		self.action_type = self.data.get("type")

		self.init_handler()
		self.handle_webhook()

	def get_or_create_invoice(self):
		pass