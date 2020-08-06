# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from erpnext.erpnext_integrations.webhooks_controller import WebhooksController

EVENT_MAP = {
	'customer_approval_granted': 'change_mandate_status',
	'customer_approval_skipped': 'change_mandate_status',
	'active': 'change_mandate_status',
	'cancelled': 'change_mandate_status',
	'failed': 'change_mandate_status',
	'transferred': 'change_mandate_status',
	'expired': 'change_mandate_status',
	'submitted': 'change_mandate_status',
	'resubmission_requested': 'change_mandate_status',
	'reinstated': 'change_mandate_status',
	'replaced': 'change_mandate_status',
	'created': 'change_mandate_status'
}

STATUS_MAP = {
	'customer_approval_granted': 'Pending Customer Approval',
	'customer_approval_skipped': 'Pending Submission',
	'active': 'Active',
	'cancelled': 'Cancelled',
	'failed': 'Failed',
	'transferred': 'Submitted',
	'expired': 'Expired',
	'submitted': 'Submitted',
	'resubmission_requested': 'Pending Submission',
	'reinstated': 'Active',
	'replaced': 'Cancelled',
	'created': 'Pending Submission'
}

class GoCardlessMandateWebhookHandler(WebhooksController):
	def __init__(self, **kwargs):
		super(GoCardlessMandateWebhookHandler, self).__init__(**kwargs)
		
		self.event_map = EVENT_MAP
		self.action_type = self.data.get("action")
		self.mandate = self.data.get("links", {}).get("mandate")
		self.handle_update()
		self.add_mandate_to_integration_request()

	def check_existing_mandate(self):
		return False if frappe.db.exists("Sepa Mandate", dict(mandate=mandate)) else True

	def change_mandate_status(self):
		self.set_status(self.mandate, STATUS_MAP.get(self.data.get("action")))

	def set_status(self, mandate, status):
		try:
			frappe.db.set_value("Sepa Mandate", mandate, "status", status)
			self.integration_request.update_status({}, "Completed")
		except Exception as e:
			self.integration_request.db_set("error", str(e))
			self.integration_request.update_status({}, "Failed")

	def add_mandate_to_integration_request(self):
		self.integration_request.db_set("reference_doctype", "Sepa Mandate")
		self.integration_request.db_set("reference_docname", self.mandate)
