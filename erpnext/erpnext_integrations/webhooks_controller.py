# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import nowdate, getdate
from datetime import timedelta
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

class WebhooksController():
	def __init__(self, **kwargs):
		self.integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))
		self.integration_request.db_set("error", None)
		self.data = json.loads(self.integration_request.get("data"))
		self.reference_date = nowdate()
		self.metadata = {}

	def handle_update(self):
		target = self.event_map.get(self.action_type)
		if not target:
			self.set_as_not_handled()
		else:
			method = getattr(self, target)
			try:
				method()
			except Exception as e:
				self.set_as_failed(frappe.get_traceback())

	def create_payment(self, reference=None):
		if not reference:
			reference = self.integration_request.get("service_id")

		if not frappe.db.exists("Payment Entry", dict(reference_no=reference, docstatus=("!=", 2))):
			if self.metadata.get("payment_request"):
				payment_request = frappe.get_doc("Payment Request", self.metadata.get("payment_request"))
				payment_entry = payment_request.run_method("create_payment_entry", submit=False)
				payment_entry.reference_no = reference
				payment_entry.payment_request = payment_request.name
				self.add_subscription_references(payment_request, payment_entry)
				payment_entry.insert(ignore_permissions=True)
				self.set_references(payment_entry.doctype, payment_entry.name)
				self.set_as_completed()

			elif self.metadata.get("reference_doctype") in ("Sales Order", "Sales Invoice"):
				payment_entry = get_payment_entry(self.metadata.get("reference_doctype"), self.metadata.get("reference_name"))
				payment_entry.reference_no = reference
				payment_entry.insert(ignore_permissions=True)
				self.set_references(payment_entry.doctype, payment_entry.name)
				self.set_as_completed()

			elif self.metadata.get("reference_doctype") == "Subscription":
				subscription = frappe.get_doc(self.metadata.get("reference_doctype"), self.metadata.get("reference_name"))
				payment_entry = subscription.run_method("create_payment")
				payment_entry.reference_no = reference
				payment_entry.subscription = subscription.name
				self.add_subscription_references(payment_request, payment_entry)
				payment_entry.insert(ignore_permissions=True)
				self.set_references(payment_entry.doctype, payment_entry.name)
				self.set_as_completed()

			else:
				self.set_as_failed(_("The reference doctype should be a Payment Request, a Sales Invoice, a Sales Order or a Subscription"))
		else:
			payment_entry = frappe.get_doc("Payment Entry", dict(reference_no=reference))
			self.set_references(payment_entry.doctype, payment_entry.name)
			self.set_as_completed()

	def submit_payment(self, reference=None):
		if not reference:
			reference = self.integration_request.get("service_id")

		if frappe.db.exists("Payment Entry", dict(reference_no=reference, docstatus=0)):
			posting_date = getdate(frappe.parse_json(self.integration_request.data).get("created_at"))
			payment_entry = frappe.get_doc("Payment Entry", dict(reference_no=reference, docstatus=0))
			payment_entry.posting_date = posting_date
			payment_entry.reference_date = posting_date

			if self.metadata.get("payment_request"):
				payment_request = frappe.get_doc("Payment Request", self.metadata.get("payment_request"))
				self.add_subscription_references(payment_request, payment_entry)

			if hasattr(self, 'add_fees_before_submission'):
				self.add_fees_before_submission(payment_entry)
			payment_entry.flags.ignore_permissions = True
			payment_entry.submit()

			self.set_references(payment_entry.doctype, payment_entry.name)
			self.set_as_completed()
		elif frappe.db.exists("Payment Entry", dict(reference_no=reference, docstatus=1)):
			payment_entry_name = frappe.db.get_value("Payment Entry", dict(reference_no=reference, docstatus=1))
			self.set_references("Payment Entry", payment_entry_name)
			self.set_as_completed()
		else:
			self.set_as_failed(_("Payment entry with reference {0} not found").format(reference))

	def add_subscription_references(self, payment_request, payment_entry):
		if payment_request.is_linked_to_a_subscription():
			payment_entry.subscription = payment_request.is_linked_to_a_subscription()
			subscription = payment_request.get_linked_subscription()
			references = subscription.get_references_for_payment_request(payment_request.name)
			if references:
				payment_entry.append('references', references)

	def cancel_payment(self, reference=None):
		if not reference:
			reference = self.integration_request.get("service_id")

		if frappe.db.exists("Payment Entry", dict(reference_no=reference)):
			payment_entry = frappe.get_doc("Payment Entry", dict(reference_no=reference))
			payment_entry.cancel()
			self.set_references(payment_entry.doctype, payment_entry.name)
			self.set_as_completed()
		else:
			self.set_as_failed(_("Payment entry with reference {0} not found").format(reference))

	def set_references(self, dt, dn):
		self.integration_request.db_set("reference_doctype", dt, update_modified=False)
		self.integration_request.db_set("reference_docname", dn, update_modified=False)
		self.integration_request.load_from_db()

	def set_as_not_handled(self):
		self.integration_request.db_set("error", _("This type of event is not handled"), update_modified=False)
		self.integration_request.load_from_db()
		self.integration_request.update_status({}, "Not Handled")

	def set_as_failed(self, message):
		self.integration_request.db_set("error", str(message), update_modified=False)
		self.integration_request.load_from_db()
		self.integration_request.update_status({}, "Failed")

	def set_as_completed(self, message=None):
		if message:
			self.integration_request.db_set("error", str(message), update_modified=False)
			self.integration_request.load_from_db()
		self.integration_request.update_status({}, "Completed")


def handle_webhooks(handlers, **kwargs):
	integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))

	if handlers.get(integration_request.get("service_document")):
		handlers.get(integration_request.get("service_document"))(**kwargs)
	else:
		integration_request.db_set("error", _("This type of event is not handled"))
		integration_request.update_status({}, "Not Handled")