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
		self.invoice = None
		self.subscription = None
		self.reference_date = nowdate()

	def handle_invoice_update(self):
		target = self.event_map.get(self.action_type)
		if not target:
			self.integration_request.db_set("error", _("This type of event is not handled by dokos"))
			self.integration_request.update_status({}, "Not Handled")

		else:
			method = getattr(self, target)
			method()

	def get_corresponding_invoice(self):
		if frappe.db.exists("Sales Invoice", dict(external_reference=self.integration_request.get("service_id"))):
			self.invoice = frappe.get_doc("Sales Invoice", dict(external_reference=self.integration_request.get("service_id")))

		if not self.invoice and self.subscription:
			self.subscription.flags.ignore_permissions = True
			self.subscription.process(True)
			invoice = self.subscription.get_current_invoice()

			if invoice and invoice.to_date > getdate(nowdate()) and \
				(abs(getdate(invoice.due_date) - getdate(self.reference_date)) < timedelta(days=11)):
				self.invoice = invoice
				self.invoice.flags.ignore_permissions = True

			else:
				self.get_closest_invoice(self.subscription.customer)

		elif not self.invoice:
			metadata = getattr(self.get_payment_document(), "metadata")
			if "reference_doctype" in metadata and "reference_document" in metadata:
				reference = frappe.db.get_value(metadata.get("reference_doctype"), metadata.get("reference_document"), \
					["reference_doctype", "reference_name"], as_dict=True)
				reference_customer = frappe.db.get_value(reference.get("reference_doctype"), reference.get("reference_name"), "customer")
				self.get_closest_invoice(reference_customer)

	def get_closest_invoice(self, customer):
		invoices = frappe.get_all("Sales Invoice", \
			filters={"customer": customer, "external_reference": ["is", "not set"]}, fields=["name", "due_date"])
		if invoices:
			closest_invoice =  min(invoices, key=lambda x: abs(getdate(x.get("due_date")) - self.reference_date))
			if closest_invoice:
				self.invoice = frappe.get_doc("Sales Invoice", closest_invoice.get("name"))

	def find_invoice(self):
		try:
			if self.invoice and self.invoice.external_reference == self.integration_request.get("service_id"):
				self.set_as_completed()

			elif self.invoice and not self.invoice.external_reference == self.integration_request.get("service_id"):
				if frappe.db.exists("Sales Invoice", dict(external_reference=self.integration_request.get("service_id"))):
					self.set_as_failed(_("An invoice ({0}) with reference {1} exists already").format(\
						self.invoice.name, self.integration_request.get("service_id")))
				elif not self.invoice.external_reference:
					self.invoice.db_set("external_reference", self.integration_request.get("service_id"))
					self.integration_request.update_status({}, "Completed")
				else:
					self.set_as_failed(_("Subscription {0} has already invoice {1} for the current period, but the invoice references don't match. Please check your subscription.").format(\
						self.subscription.name, self.invoice.name))

			elif self.subscription:
				self.subscription.reload()
				self.subscription.process_active_subscription()
				self.invoice = self.subscription.get_current_invoice()
				if self.invoice and (abs(getdate(self.invoice.due_date) - getdate(frappe.parse_json(self.integration_request.data).get("created_at"))) < timedelta(days=11)):
					self.invoice.db_set("external_reference", self.integration_request.get("service_id"))
					self.integration_request.update_status({}, "Completed")
				else:
					self.set_as_failed(_("The corresponding invoice could not be found"))

			elif frappe.db.exists("Sales Order", dict(external_reference=self.integration_request.get("service_id"))):
				self.create_invoice_from_sales_order()

			else:
				self.set_as_failed(_("Please create a new invoice for this event with external reference {0}").format(self.integration_request.get("service_id")))
		except Exception as e:
			self.set_as_failed(e)

	def create_invoice_from_sales_order(self):
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
		self.so_name = frappe.db.get_value("Sales Order", dict(external_reference=self.integration_request.get("service_id")), "name")
		self.invoice = make_sales_invoice(self.so_name)
		self.invoice.insert()

	def delete_invoice(self):
		self.cancel_invoice()

	def cancel_invoice(self):
		try:
			if self.invoice.get("name") == frappe.db.get_value("Sales Invoice", dict(external_reference=self.integration_request.get("service_id")), "name"):
				self.invoice.cancel()
				self.integration_request.update_status({}, "Completed")
			else:
				self.set_as_failed(_("Sales invoice with external reference {0} could not be found").format(self.integration_request.get("service_id")))
		except Exception as e:
			self.set_as_failed(e)

	def pay_invoice(self):
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		try:
			if not self.invoice:
				self.set_as_failed(_("Sales invoice with external reference {0} could not be found").format(\
					self.integration_request.get("service_id")))
			else:
				if self.invoice.get("docstatus") == 1:
					posting_date = getdate(frappe.parse_json(self.integration_request.data).get("created_at"))
					self.payment_entry = get_payment_entry("Sales Invoice", self.invoice.name)
					self.payment_entry.posting_date = posting_date
					self.payment_entry.reference_no = self.integration_request.get("service_id") or self.integration_request.name
					self.payment_entry.reference_date = posting_date

					if hasattr(self, 'add_fees_before_creation'):
						self.add_fees_before_creation()
					self.payment_entry.flags.ignore_permissions = True
					self.payment_entry.insert()
					self.integration_request.update_status({}, "Completed")
				elif self.invoice.get("docstatus") == 2:
					self.set_as_failed(_("Current invoice {0} is cancelled").format(self.invoice.name))
				else:
					self.set_as_failed(_("Current invoice {0} is not submitted").format(self.invoice.name))
		except Exception as e:
			self.set_as_failed(e)

	def submit_payment(self):
		try:
			if frappe.db.exists("Payment Entry", dict(reference_no=self.integration_request.get("service_id"))):
				posting_date = getdate(frappe.parse_json(self.integration_request.data).get("created_at"))
				self.payment_entry = frappe.get_doc("Payment Entry", dict(reference_no=self.integration_request.get("service_id")))
				self.payment_entry.posting_date = posting_date
				self.payment_entry.reference_date = posting_date
				if hasattr(self, 'add_fees_before_submission'):
					self.add_fees_before_submission()
				self.payment_entry.submit()
			else:
				self.set_as_failed(_("Payment entry with reference {0} not found").format(self.integration_request.get("service_id")))
		except Exception as e:
			self.set_as_failed(e)

	def create_and_submit_payment(self):
		try:
			self.pay_invoice()
			if hasattr(self, 'payment_entry') and self.payment_entry:
				self.payment_entry.submit()
		except Exception as e:
			self.set_as_failed(e)

	#TODO: Add missing methods
	def fail_invoice(self):
		self.set_as_completed(_("Invoice payment failed. Please check it manually."))

	def create_credit_note(self):
		self.set_as_completed(_("Credit note to be created manually."))

	def cancel_credit_note(self):
		self.set_as_completed(_("Credit note to be cancelled manually."))

	def change_status(self):
		self.integration_request.db_set("error", _("This type of event is not handled by dokos"))
		self.integration_request.update_status({}, "Not Handled")

	def add_reference_to_integration_request(self):
		if self.invoice:
			self.integration_request.db_set("reference_doctype", "Sales Invoice")
			self.integration_request.db_set("reference_docname", self.invoice.name if self.invoice else None)

	def set_as_failed(self, message):
		self.integration_request.db_set("error", str(message))
		self.integration_request.update_status({}, "Failed")

	def set_as_completed(self, message):
		self.integration_request.db_set("error", str(message))
		self.integration_request.update_status({}, "Completed")
