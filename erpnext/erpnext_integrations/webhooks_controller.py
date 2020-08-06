# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import nowdate, getdate
from datetime import timedelta

class WebhooksController():
	def __init__(self, **kwargs):
		self.integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))
		self.integration_request.db_set("error", None)
		self.data = json.loads(self.integration_request.get("data"))
		self.order = None
		self.invoice = None
		self.subscription = None
		self.payment_entry = None
		self.payment_request = None
		self.reference_date = nowdate()
		self.metadata = {}

		self.document_map = {
			"Sales Invoice": self.invoice,
			"Sales Order": self.order,
			"Subscription": self.subscription
		}

	def handle_payment_update(self):
		target = self.event_map.get(self.action_type)
		if not target:
			self.integration_request.db_set("error", _("This type of event is not handled"))
			self.integration_request.update_status({}, "Not Handled")

		else:
			method = getattr(self, target)
			try:
				method()
			except Exception as e:
				self.set_as_failed(frappe.get_traceback())

	def get_reference_doc(self):
		reference_document = self.document_map.get(self.metadata.get("reference_doctype"))
		if frappe.db.exists(self.metadata.get("reference_doctype"), self.metadata.get("reference_name")):
			reference_document = frappe.get_doc(self.metadata.get("reference_doctype"), self.metadata.get("reference_name"))

	def create_payment(self, reference=None):
		if not reference:
			reference = self.integration_request.get("service_id")

		if not frappe.db.exists("Payment Entry", dict(reference_no=reference, docstatus=("!=", 2))):
			if self.metadata.get("reference_doctype") == "Payment Request":
				pr = frappe.get_doc(self.metadata.get("reference_doctype"), self.metadata.get("reference_name"))
				self.payment_entry = pr.run_method("create_payment_entry", submit=False)
				self.payment_entry.reference_no = reference
				self.payment_entry.insert(ignore_permissions=True)
				self.set_as_completed()

			elif self.metadata.get("reference_doctype") == "Subscription":
				subscription = frappe.get_doc(self.metadata.get("reference_doctype"), self.metadata.get("reference_name"))
				self.payment_entry = subscription.run_method("create_payment")
				self.payment_entry.reference_no = reference
				self.payment_entry.insert(ignore_permissions=True)
				self.set_as_completed()

			else:
				self.set_as_failed(_("The reference doctype should be a Payment Request or a Subscription"))
		else:
			self.payment_entry = frappe.get_doc("Payment Entry", dict(reference_no=reference))
			self.set_as_completed()

	def submit_payment(self, reference=None):
		if not reference:
			reference = self.integration_request.get("service_id")

		if frappe.db.exists("Payment Entry", dict(reference_no=reference, docstatus=0)):
			posting_date = getdate(frappe.parse_json(self.integration_request.data).get("created_at"))
			self.payment_entry = frappe.get_doc("Payment Entry", dict(reference_no=reference, docstatus=0))
			self.payment_entry.posting_date = posting_date
			self.payment_entry.reference_date = posting_date

			if hasattr(self, 'add_fees_before_submission'):
				self.add_fees_before_submission()
			self.payment_entry.flags.ignore_permissions = True
			self.payment_entry.submit()

			self.trigger_subscription_events()

			self.set_as_completed()
		elif frappe.db.exists("Payment Entry", dict(reference_no=reference, docstatus=1)):
			self.set_as_completed()
		else:
			self.set_as_failed(_("Payment entry with reference {0} not found").format(reference))

	def cancel_payment(self, reference=None):
		if not reference:
			reference = self.integration_request.get("service_id")

		if frappe.db.exists("Payment Entry", dict(reference_no=reference)):
			self.payment_entry = frappe.get_doc("Payment Entry", dict(reference_no=reference))
			self.payment_entry.cancel()
			self.set_as_completed()
		else:
			self.set_as_failed(_("Payment entry with reference {0} not found").format(reference))

	def trigger_subscription_events(self):
		if self.metadata.get("reference_doctype") == "Subscription":
			self.subscription = frappe.get_doc(self.metadata.get("reference_doctype"), self.metadata.get("reference_name"))
			if self.subscription.status == 'Active':
				self.subscription.flags.ignore_permissions = True
				self.subscription.run_method("process_active_subscription", payment_entry=self.payment_entry.name)
				frappe.db.commit()

	def change_status(self):
		self.integration_request.db_set("error", _("This type of event is not handled"))
		self.integration_request.update_status({}, "Not Handled")

	def add_reference_to_integration_request(self):
		if self.payment_entry:
			self.integration_request.db_set("reference_doctype", "Payment Entry")
			self.integration_request.db_set("reference_docname", self.payment_entry.name)

		elif self.invoice:
			self.integration_request.db_set("reference_doctype", "Sales Invoice")
			self.integration_request.db_set("reference_docname", self.invoice.name)

		elif self.order:
			self.integration_request.db_set("reference_doctype", "Sales Order")
			self.integration_request.db_set("reference_docname", self.order.name)

	def set_as_failed(self, message):
		self.integration_request.db_set("error", str(message))
		self.integration_request.update_status({}, "Failed")

	def set_as_completed(self, message=None):
		if message:
			self.integration_request.db_set("error", str(message))
		self.integration_request.reload()
		self.integration_request.update_status({}, "Completed")
