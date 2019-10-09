# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import nowdate

class WebhooksController():
	def __init__(self, **kwargs):
		self.integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))
		self.integration_request.db_set("error", None)
		self.data = json.loads(self.integration_request.get("data"))
		self.invoice = None
		self.subscription = None

	def handle_invoice_update(self):
		target = self.event_map.get(self.action_type)
		if not target:
			self.integration_request.db_set("error", _("This type of event is not handled by dokos"))
			self.integration_request.update_status({}, "Not Handled")

		else:
			method = getattr(self, target)
			method()

	def get_subscription_invoice(self):
		if self.subscription:
			self.subscription.flags.ignore_permissions = True
			self.subscription.process()
			self.invoice = self.subscription.get_current_invoice()
			if self.invoice:
				self.invoice.flags.ignore_permissions = True

	def get_one_off_invoice(self):
		if frappe.db.exists("Sales Invoice", dict(external_reference=self.integration_request.get("service_id"))):
			self.invoice = frappe.get_doc("Sales Invoice", dict(external_reference=self.integration_request.get("service_id")))

	def create_invoice(self):
		try:
			if self.invoice and frappe.db.exists("Sales Invoice", dict(external_reference=self.integration_request.get("service_id"))):
				self.set_as_completed(_("An invoice {0} with reference {1} exists already").format(\
					self.invoice.name, self.integration_request.get("service_id")))

			elif self.invoice and not frappe.db.exists("Sales Invoice", dict(external_reference=self.integration_request.get("service_id"))):
				if not self.invoice.external_reference:
					self.invoice.db_set("external_reference", self.integration_request.get("service_id"))
					self.integration_request.update_status({}, "Completed")
				else:
					self.set_as_failed(_("Subscription {0} has already invoice {1} for the current period, but the invoice references don't match. Please check your subscription.").format(\
						self.subscription.name, self.invoice.name))

			elif self.subscription:
				self.subscription.process_active_subscription()
				self.invoice = self.subscription.get_current_invoice()
				if self.invoice:
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
		self.invoice.save()

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
					self.payment_entry = get_payment_entry("Sales Invoice", self.invoice.name)
					self.payment_entry.reference_no = self.integration_request.get("service_id") or self.integration_request.name
					self.payment_entry.reference_date = nowdate()
					if hasattr(self, 'add_fees'):
						self.add_fees()
					self.payment_entry.flags.ignore_permissions = True
					self.payment_entry.insert()
					self.payment_entry.submit()
					self.integration_request.update_status({}, "Completed")
				elif self.invoice.get("docstatus") == 2:
					self.set_as_failed(_("Current invoice {0} is cancelled").format(self.invoice.name))
				else:
					self.set_as_failed(_("Current invoice {0} is not submitted").format(self.invoice.name))
		except Exception as e:
			print(frappe.get_traceback())
			self.set_as_failed(e)

	#TODO: Add missing methods
	def fail_invoice(self):
		self.set_as_completed(_("Invoice payment failed. Please check it manually."))

	def create_credit_note(self):
		self.set_as_completed(_("Credit note to be created manually."))

	def cancel_credit_note(self):
		self.set_as_completed(_("Credit note to be cancelled manually."))

	def reconcile_payment(self):
		self.set_as_completed(_("Payment to be reconciled manually."))

	def change_status(self):
		pass

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
