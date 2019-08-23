# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import gocardless_pro
from frappe import _
from urllib.parse import urlencode
from frappe.utils import get_url, call_hook_method, flt, cint
from frappe.integrations.utils import create_request_log, create_payment_gateway, finalize_request
import json

class GoCardlessSettings(Document):
	supported_currencies = ["EUR", "DKK", "GBP", "SEK"]

	interval_map = {
		"Week": "weekly",
		"Month": "monthy",
		"Year": "yearly"
	}

	def validate(self):
		self.initialize_client()

	def initialize_client(self):
		self.environment = self.get_environment()
		try:
			self.client = gocardless_pro.Client(
				access_token=self.access_token,
				environment=self.environment
				)
			return self.client
		except Exception as e:
			frappe.throw(e)

	def on_update(self):
		create_payment_gateway('GoCardless-' + self.gateway_name, settings='GoCardLess Settings', controller=self.gateway_name)
		call_hook_method('payment_gateway_enabled', gateway='GoCardless-' + self.gateway_name)

	def validate_subscription_plan(self, currency, plan=None):
		if currency in supported_currencies:
			return self.initialize_client()
		else:
			frappe.throw("The currency {0} is not supported by GoCardless").format(currency)

	def on_payment_request_submission(self, data):
		try:
			data = frappe.db.get_value(data.reference_doctype, data.reference_name, "customer_name as payer_name", as_dict=1)
			return self.check_mandate_validity(data)

		except Exception:
			frappe.log_error(frappe.get_traceback(), _("GoCardless mandate validation failed for {0}".format(data.get("payer_name"))))

	def immediate_payment_processing(self, data):
		try:
			customer_data = frappe.db.get_value(data.reference_doctype, data.reference_name,\
				["company", "customer_name"], as_dict=1)

			data = {
				"amount": flt(data.grand_total, data.precision("grand_total")),
				"title": customer_data.company.encode("utf-8"),
				"description": data.subject.encode("utf-8"),
				"reference_doctype": data.doctype,
				"reference_docname": data.name,
				"payer_email": data.email_to or frappe.session.user,
				"payer_name": customer_data.customer_name,
				"order_id": data.name,
				"currency": data.currency
			}

			valid_mandate = self.check_mandate_validity(data)
			if valid_mandate:
				data.update(valid_mandate)

				return self.create_payment_request(data)

		except Exception:
			frappe.log_error(frappe.get_traceback(),\
				_("GoCardless direct processing failed for {0}".format(customer_data.customer_name)))

	def check_mandate_validity(self, data):
		if frappe.db.exists("GoCardless Mandate", dict(customer=data.get('payer_name'),\
			status=["not in", ["Cancelled", "Expired", "Failed"]])):
			self.initialize_client()

			registered_mandate = frappe.db.get_value("GoCardless Mandate",\
				dict(customer=data.get('payer_name'), status=["not in", ["Cancelled", "Expired", "Failed"]]), 'mandate')
			mandate = self.client.mandates.get(registered_mandate)

			if mandate.status == "pending_customer_approval" or mandate.status == "pending_submission"\
				or mandate.status == "submitted" or mandate.status == "active":
				return {
					"mandate": registered_mandate
				}

	def create_new_mandate(self):
		self.initialize_client()
		mandate = self.client.mandates.get(registered_mandate)

	def get_environment(self):
		return 'sandbox' if self.use_sandbox else 'live'

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. Stripe does not support transactions in currency '{0}'").format(currency))

	def get_payment_url(self, **kwargs):
		return get_url("./integrations/gocardless_checkout?{0}".format(urlencode(kwargs)))

	def create_payment_request(self, data):
		self.data = frappe._dict(data)

		try:
			self.integration_request = create_request_log(self.data, "Payment", "GoCardless")
			self.reference_document = frappe.get_doc(self.data.reference_doctype, self.data.reference_docname)

			self.subscription = False
			if hasattr(self.reference_document, 'is_linked_to_a_subscription'):
				self.subscription = self.reference_document.is_linked_to_a_subscription()

			self.initialize_client()
			if self.subscription:
				return self.create_new_subscription()
			else:
				return self.create_charge_on_gocardless()

		except Exception as e:
			self.integration_request.db_set('status', 'Failed', update_modified=True)
			self.integration_request.db_set('error', str(e), update_modified=True)
			frappe.log_error(frappe.get_traceback(), "GoCardless payment creation error")
			return self.error_message(402)

	def create_new_subscription(self):
		subscription = frappe.get_doc("Subscription", self.subscription)
		plan_details = frappe.db.get_value("Subscription Plan", subscription.plans[0].get("plan"),\
			["billing_interval", "billing_interval_count"], as_dict=1)

		if not plan_details.billing_interval or plan_details.billing_interval == "Day":
			return self.create_charge_on_gocardless()
		else:
			try:
				self.output = self.client.subscriptions.create(
					params={
						"amount": flt(self.reference_document.grand_total) * 100,
						"currency": self.reference_document.currency,
						"name": subscription.name,
						"interval_unit": interval_map[plan_details.billing_interval],
						"interval": plan_details.billing_interval_count,
						"day_of_month":  self.reference_document.transaction_date\
							if plan_details.billing_interval == "Month" else "",
						"metadata": {
							"order_no": self.reference_document.reference_name
						},
						"links": {
							"mandate": self.data.get("mandate")
						}		
					},
					headers={
						'Idempotency-Key' : self.data.get('reference_docname'),
					}
				)

				self.process_output()

			except Exception as e:
				self.integration_request.db_set('error', str(e), update_modified=True)
				frappe.log_error(frappe.get_traceback(), _("GoCardless subscription creation error"))

			return finalize_request(self)

	def create_charge_on_gocardless(self):
		try:
			self.output = self.client.payments.create(
				params={
					"amount" : cint(self.reference_document.grand_total * 100),
					"currency" : self.reference_document.currency,
					"links" : {
						"mandate": self.data.get('mandate')
					},
					"metadata": {
					  "reference_doctype": self.reference_document.doctype,
					  "reference_document": self.reference_document.name
					}
				},
				headers={
					'Idempotency-Key' : self.data.get('reference_docname'),
				}
			)

			self.process_output()

		except Exception as e:
			self.integration_request.db_set('error', str(e), update_modified=True)
			frappe.log_error(frappe.get_traceback(), "GoCardless Payment Error")

		return finalize_request(self)

	def process_output(self):
		print(self.output.status)
		if self.output.status == "pending_submission" or self.output.status == "pending_customer_approval"\
			or self.output.status == "submitted":
			self.integration_request.db_set('status', 'Authorized', update_modified=True)
			self.flags.status_changed_to = "Completed"
			self.integration_request.db_set('output', str(self.output.__dict__), update_modified=True)

		elif self.output.status == "confirmed" or self.output.status == "paid_out":
			self.integration_request.db_set('status', 'Completed', update_modified=True)
			self.flags.status_changed_to = "Completed"
			self.integration_request.db_set('output', str(self.output.__dict__), update_modified=True)

		elif self.output.status == "cancelled" or self.output.status == "customer_approval_denied"\
			or self.output.status == "charged_back":
			self.integration_request.db_set('status', 'Cancelled', update_modified=True)
			self.flags.status_changed_to = "Failed"
			frappe.log_error(_("Payment Cancelled. Please check your GoCardless Account for more details"), "GoCardless Payment Error")
			self.integration_request.db_set('error', str(self.output.__dict__), update_modified=True)
		else:
			self.integration_request.db_set('status', 'Failed', update_modified=True)
			self.flags.status_changed_to = "Failed"
			frappe.log_error(_("Payment Failed. Please check your GoCardless Account for more details"), "GoCardless Payment Error")
			self.integration_request.db_set('error', str(self.output.__dict__), update_modified=True)

	def error_message(self, error_number=500):
		if error_number == 402:
			return {
					"redirect_to": frappe.redirect_to_message(_('Server Error'),\
						_("It seems that there is an issue with our GoCardless integration.\
						<br>In case of failure, the amount will get refunded to your account.")),
					"status": 402
				}
		else:
			return {
					"redirect_to": frappe.redirect_to_message(_('Server Error'),\
						_("It seems that there is an issue with our GoCardless integration.\
						<br>In case of failure, the amount will get refunded to your account.")),
					"status": 500
				}

def get_gateway_controller(doctype, docname):
	payment_request = frappe.get_doc(doctype, docname)
	gateway_controller = frappe.db.get_value("Payment Gateway",\
		payment_request.payment_gateway, "gateway_controller")
	return gateway_controller

def check_mandate_validity_daily():
	settings_documents = frappe.get_all("GoCardless Settings", filters={"mandate_validity_check": 1})
	for settings in settings_documents:
		customers = frappe.get_all("Integration References",\
			filters={"gocardless_settings": settings.name}, fields=["customer"])
		if customers:
			provider = frappe.get_doc("GoCardless Settings", settings.name)
			provider.initialize_client()
			for customer in customers:
				mandates = frappe.get_all("GoCardless Mandate", filters={"customer": customer.customer})
				if mandates:
					for mandate in mandates:
						result = provider.client.mandates.get(mandate.name)
						frappe.db.set_value("GoCardless Mandate", mandate.name, "status",\
							result.status.replace("_", " ").capitalize())

