# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import nowdate, getdate
from datetime import timedelta
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.subscription.subscription_state_manager import SubscriptionPeriod
from erpnext.accounts.doctype.subscription.subscription_transaction import SubscriptionInvoiceGenerator

class WebhooksController():
	def __init__(self, **kwargs):
		self.integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))
		self.integration_request.db_set("error", None)
		self.data = json.loads(self.integration_request.get("data"))
		self.reference_date = nowdate()
		self.metadata = {}
		self.payment_request = None
		self.subscription = None
		self.sales_invoice = None
		self.sales_order = None

	def handle_update(self):
		self.process_metadata()
		target = self.event_map.get(self.action_type)
		if not target:
			self.set_as_not_handled()
		else:
			method = getattr(self, target)
			try:
				method()
			except Exception as e:
				self.set_as_failed(frappe.get_traceback())

	def process_metadata(self):
		if self.metadata.get("reference_doctype"):
			reference_doc = frappe.get_doc(self.metadata.get("reference_doctype"), self.metadata.get("reference_doctype"))

		if reference_doc.doctype == "Subscription" and not self.subscription:
			self.subscription = reference_doc

		if reference_doc.doctype == "Sales Invoice" and not self.sales_invoice:
			self.sales_invoice = reference_doc

		if reference_doc.doctype =="Sales Order" and not self.sales_order:
			self.sales_order = reference_doc

	def create_payment(self, reference=None):
		if not reference:
			reference = self.integration_request.get("service_id")

		if not frappe.db.exists("Payment Entry", dict(reference_no=reference, docstatus=("!=", 2))):
			if self.payment_request:
				payment_entry = self.payment_request.run_method("create_payment_entry", submit=False)
				payment_entry.reference_no = reference
				payment_entry.payment_request = self.payment_request.name
				self.add_subscription_references(self.payment_request, payment_entry)
				payment_entry.insert(ignore_permissions=True)
				self.set_references(payment_entry.doctype, payment_entry.name)
				self.set_as_completed()

			# Kept for compatibility.
			# All new request should contain a payment_request key in their metadata or provide a way to obtain it in the handler (for subscriptions).
			elif self.metadata.get("reference_doctype") in ("Sales Order", "Sales Invoice"):
				payment_entry = get_payment_entry(self.metadata.get("reference_doctype"), self.metadata.get("reference_name"))
				payment_entry.reference_no = reference
				payment_entry.payment_request = self.payment_request.name if self.payment_request else None
				payment_entry.insert(ignore_permissions=True)
				self.set_references(payment_entry.doctype, payment_entry.name)
				self.set_as_completed()

			elif self.subscription:
				payment_entry = subscription.run_method("create_payment")
				payment_entry.reference_no = reference
				payment_entry.subscription = self.subscription.name
				if self.payment_request:
					payment_entry.payment_request = self.payment_request.name
					self.add_subscription_references(self.payment_request, payment_entry)
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

			if self.payment_request:
				self.add_subscription_references(self.payment_request, payment_entry)

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
		if self.subscription:
			payment_entry.subscription = payment_request.is_linked_to_a_subscription()
			references = self.subscription.get_references_for_payment_request(payment_request.name)
			for ref in references:
				payment_entry.append('references', ref)

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

	def get_sales_invoice(self, reference=None, start=None, end=None):
		invoice = None
		if reference:
			invoice = frappe.db.get_value("Sales Invoice", {"external_reference": reference, "docstatus": ("!=", 2)})

		if not invoice and self.subscription:
			invoices = SubscriptionPeriod(subscription,
				start=start,
				end=end
			).get_current_documents("Sales Invoice")

			if invoices:
				return invoices[0].name

		return invoice

	def create_sales_invoice(self, period_start, period_end, reference=None):
		invoice = None
		if self.subscription:
			invoice = SubscriptionInvoiceGenerator(
				self.subscription,
				start_date=period_start,
				end_date=period_end,
			).create_invoice()
		elif self.sales_invoice:
			invoice = self.sales_invoice.name
		elif self.sales_order:
			from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
			invoice = make_sales_invoice(self.sales_order.name, ignore_permissions=True)
			invoice.allocate_advances_automatically = True
			invoice.insert(ignore_permissions=True)

		if invoice:
			frappe.db.set_value("Sales Invoice", invoice.name, "external_reference", self.data.get("data", {}).get("object", {}).get("id"))
		return invoice

	def submit_sales_invoice(self, reference=None):
		if not reference:
			reference = self.data.get("data", {}).get("object", {}).get("id")

		invoice = get_sales_invoice(self, reference)
		invoice.submit()

	def cancel_sales_invoice(self, reference=None):
		if not reference:
			reference = self.data.get("data", {}).get("object", {}).get("id")

		invoice = get_sales_invoice(self, reference)
		if invoice.docstatus == 1:
			invoice.cancel()
		elif invoice.docstatus == 0:
			invoice.delete()

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