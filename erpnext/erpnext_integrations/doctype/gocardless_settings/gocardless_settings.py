# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import gocardless_pro
from frappe import _
from urllib.parse import urlencode
from frappe.utils import get_url, call_hook_method, flt, cint, nowdate, get_last_day, getdate
from frappe.integrations.utils import PaymentGatewayController,\
	create_request_log, create_payment_gateway
from erpnext.erpnext_integrations.doctype.gocardless_settings.webhooks_documents.mandate import GoCardlessMandateWebhookHandler
from erpnext.erpnext_integrations.doctype.gocardless_settings.webhooks_documents.payment import GoCardlessPaymentWebhookHandler
import json

class GoCardlessSettings(PaymentGatewayController):
	supported_currencies = ["EUR", "DKK", "GBP", "SEK"]

	interval_map = {
		"Week": "weekly",
		"Month": "monthly",
		"Year": "yearly"
	}

	def __init__(self, *args, **kwargs):
		super(GoCardlessSettings, self).__init__(*args, **kwargs)
		if not self.is_new():
			self.initialize_client()

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
			frappe.throw(str(e))

	def on_update(self):
		create_payment_gateway('GoCardless-' + self.gateway_name, settings='GoCardLess Settings', controller=self.gateway_name)
		call_hook_method('payment_gateway_enabled', gateway='GoCardless-' + self.gateway_name)

	def validate_subscription_plan(self, currency, plan=None):
		if currency in self.supported_currencies:
			return self.initialize_client()
		else:
			frappe.throw("The currency {0} is not supported by GoCardless").format(currency)

	def on_payment_request_submission(self, data):
		try:
			data = frappe.db.get_value(data.reference_doctype, data.reference_name, "customer_name as payer_name", as_dict=1)
			return self.check_mandate_validity(data)

		except Exception:
			frappe.log_error(frappe.get_traceback(), _("Sepa mandate validation failed for {0}".format(data.get("payer_name"))))

	def immediate_payment_processing(self, data):
		try:
			customer_data = frappe.db.get_value(data.reference_doctype, data.reference_name,\
				["company", "customer_name"], as_dict=1)

			data = {
				"amount": cint(flt(data.grand_total, data.precision("grand_total")) * 100),
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
		if frappe.db.exists("Sepa Mandate", dict(customer=data.get('payer_name'),\
			status=["not in", ["Cancelled", "Expired", "Failed"]])):

			registered_mandate = frappe.db.get_value("Sepa Mandate",\
				dict(customer=data.get('payer_name'), status=["not in", ["Cancelled", "Expired", "Failed"]]), 'mandate')
			mandate = self.get_single_mandate(registered_mandate)

			if mandate.status == "pending_customer_approval" or mandate.status == "pending_submission"\
				or mandate.status == "submitted" or mandate.status == "active":
				return {
					"mandate": registered_mandate
				}

	def get_environment(self):
		return 'sandbox' if self.use_sandbox else 'live'

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. GoCardless does not support transactions in currency '{0}'").format(currency))

	def get_payment_url(self, **kwargs):
		return get_url("./integrations/gocardless_checkout?{0}".format(urlencode(kwargs)))

	def create_payment_request(self, data):
		self.data = frappe._dict(data)

		try:
			self.integration_request = create_request_log(self.data, "Request", "GoCardless")
			self.reference_document = frappe.get_doc(self.data.reference_doctype, self.data.reference_docname)

			self.subscription = False
			if hasattr(self.reference_document, 'is_linked_to_a_subscription'):
				self.subscription = self.reference_document.is_linked_to_a_subscription()

			if self.subscription:
				self.create_new_subscription()
			else:
				self.create_charge_on_gocardless()

			return self.finalize_request()
		except Exception as e:
			self.change_integration_request_status("Failed", "error", str(e))
			return self.error_message(402, _("GoCardless payment creation error"))

	def create_new_subscription(self):
		subscription = frappe.get_doc("Subscription", self.subscription)
		plan_details = frappe.db.get_value("Subscription Plan", subscription.plans[0].get("plan"),\
			["billing_interval", "billing_interval_count"], as_dict=1)

		if not plan_details.billing_interval or plan_details.billing_interval == "Day":
			return self.create_charge_on_gocardless()
		else:
			try:
				self.output = self.create_subscription_on_gocardless(self.reference_document, self.data, self.subscription, plan_details)
				return self.process_output('subscription')

			except Exception as e:
				self.change_integration_request_status("Failed", "error", str(e))
				return self.error_message(402, _("GoCardless subscription creation error"))

	def create_charge_on_gocardless(self):
		try:
			self.output = self.create_payment_on_gocardless(self.reference_document, self.data)
			return self.process_output('payment')
		except Exception as e:
			self.change_integration_request_status("Failed", "error", str(e))
			return self.error_message(402, _("GoCardless Payment Error"))

	def get_day_of_month(self):
		if self.reference_document.transaction_date\
			!= get_last_day(self.reference_document.transaction_date):
			return self.reference_document.transaction_date.strftime("%d")
		else:
			return -1

	def get_payments_on_gocardless(self, id=None, params=None):
		return self.get_payment_by_id(id) if id else self.get_payment_list(params)

	def get_payment_by_id(self, id):
		try:
			return self.client.payments.get(id)
		except Exception as e:
			frappe.log_error(e, _("GoCardless payment retrieval error"))

	def get_payment_list(self, params=None):
		try:
			return self.client.payments.list(params=params).records
		except Exception as e:
			frappe.log_error(e, _("GoCardless payment retrieval error"))

	def get_payout_by_id(self, id):
		try:
			return self.client.payouts.get(id)
		except Exception as e:
			frappe.log_error(e, _("GoCardless payout retrieval error"))

	def get_payout_items_list(self, params):
		try:
			return self.client.payout_items.list(params=params).records
		except Exception as e:
			frappe.log_error(e, _("GoCardless payout items retrieval error"))

	def cancel_subscription(self, **kwargs):
		try:
			return self.client.subscriptions.cancel(kwargs.get("subscription"))
		except Exception as e:
			frappe.log_error(e, _("GoCardless subscription cancellation error"))

	def get_single_mandate(self, id):
		try:
			return self.client.mandates.get(id)
		except Exception as e:
			frappe.log_error(e, _("Sepa mandate retrieval error"))

	@staticmethod
	def get_base_amount(payout_items):
		paid_amount = [x.amount for x in payout_items if x.type == "payment_paid_out"]
		total = 0
		for p in paid_amount:
			total += flt(p)
		return total / 100

	@staticmethod
	def get_fee_amount(payout_items):
		fee_amount = [x.amount for x in payout_items if x.type == "gocardless_fee" or x.type == "app_fee"]
		total = 0
		for p in fee_amount:
			total += flt(p)
		return total / 100

	@staticmethod
	def get_exchange_rate(payment):
		return flt(payment.attributes.get("fx", {}).get("amount")) or 1

	def create_subscription_on_gocardless(self, reference_document, data, subscription, plan_details):
		mandate = self.get_single_mandate(data.get("mandate"))
		return self.client.subscriptions.create(
			params={
				"amount": cint(flt(reference_document.grand_total, self.reference_document.precision("grand_total")) * 100),
				"currency": reference_document.currency,
				"name": subscription,
				"interval_unit": self.interval_map[plan_details.billing_interval],
				"interval": plan_details.billing_interval_count,
				"start_date": max(getdate(mandate.next_possible_charge_date), getdate(reference_document.transaction_date)),
				"day_of_month": self.get_day_of_month()\
					if plan_details.billing_interval == "Month" else "",
				"metadata": {
					"order_no": reference_document.reference_name
				},
				"links": {
					"mandate": data.get("mandate")
				}
			},
			headers={
				'Idempotency-Key' : data.get('reference_docname'),
			}
		)

	def create_payment_on_gocardless(self, reference_document, data):
		return self.client.payments.create(
			params={
				"amount" : cint(reference_document.grand_total * 100),
				"currency" : reference_document.currency,
				"links" : {
					"mandate": data.get('mandate')
				},
				"metadata": {
					"reference_doctype": reference_document.doctype,
					"reference_document": reference_document.name
				}
			},
			headers={
				'Idempotency-Key' : data.get('reference_docname'),
			}
		)

	def process_output(self, service):
		if service == "subscription":
			self.process_subscription()
		elif service == "payment":
			self.process_payment()

	def process_subscription(self):
		self.update_transaction_reference()
		if self.output.status == "pending_customer_approval":
			self.change_integration_request_status("Pending", "output", str(self.output.__dict__))
			self.reference_document.db_set("status", "Pending", update_modified=True)
			self.add_service_link_to_integration_request("subscription", self.output.id)

		elif self.output.status == "active" or self.output.status == "finished":
			self.change_integration_request_status("Completed", "output", str(self.output.__dict__))
			self.add_service_link_to_integration_request("subscription", self.output.id)

		elif self.output.status == "cancelled" or self.output.status == "customer_approval_denied":
			self.change_integration_request_status("Cancelled", "error", str(self.output.__dict__))
			return self.error_message(402, _("GoCardless Payment Error"),\
				_("Payment Cancelled. Please check your GoCardless Account for more details"))

		else:
			self.change_integration_request_status("Failed", "error", str(self.output.__dict__))
			return self.error_message(402, _("GoCardless Payment Error"),\
				_("Payment Failed. Please check your GoCardless Account for more details"))

	def process_payment(self):
		self.update_transaction_reference()
		if self.output.status == "pending_submission"\
			or self.output.status == "pending_customer_approval" or self.output.status == "submitted":
			self.change_integration_request_status("Pending", "output", str(self.output.__dict__))
			self.reference_document.db_set("status", "Pending", update_modified=True)
			self.add_service_link_to_integration_request("payment", self.output.id)

		elif self.output.status == "confirmed" or self.output.status == "paid_out":
			self.change_integration_request_status("Completed", "output", str(self.output.__dict__))
			self.add_service_link_to_integration_request("payment", self.output.id)

		elif self.output.status == "cancelled" or self.output.status == "customer_approval_denied"\
			or self.output.status == "charged_back":
			self.change_integration_request_status("Cancelled", "error", str(self.output.__dict__))
			return self.error_message(402, _("GoCardless Payment Error"),\
				_("Payment Cancelled. Please check your GoCardless Account for more details"))
		else:
			self.change_integration_request_status("Failed", "error", str(self.output.__dict__))
			return self.error_message(402, _("GoCardless Payment Error"),\
				_("Payment Failed. Please check your GoCardless Account for more details"))

	def update_transaction_reference(self):
		frappe.db.set_value(self.reference_document.reference_doctype, self.reference_document.reference_name,\
			"external_reference", self.output.attributes.get("id") if self.output.attributes else "")

	def change_integration_request_status(self, status, type, error):
		self.flags.status_changed_to = status
		self.integration_request.db_set('status', status, update_modified=True)
		self.integration_request.db_set(type, error, update_modified=True)
		if hasattr(self, "output"):
			self.integration_request.db_set('service_status', self.output.status, update_modified=True)

	def add_service_link_to_integration_request(self, document, id):
		self.integration_request.db_set('service_document', document, update_modified=True)
		self.integration_request.db_set('service_id', id, update_modified=True)

	def error_message(self, error_number=500, title=None, error=None):
		if error is None:
			error = frappe.get_traceback()

		frappe.log_error(error, title)
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

def check_integrated_documents():
	settings_documents = frappe.get_all("GoCardless Settings", filters={"check_for_updates": 1})
	for settings in settings_documents:
		provider = frappe.get_doc("GoCardless Settings", settings.name)
		check_mandate_status(provider)
		check_payment_status(provider)
		
		# TODO: Analyze if necessary
		# fetch_existing_payments(provider)

def check_mandate_status(provider):
	customers = frappe.get_all("Integration References",\
		filters={"gocardless_settings": provider.name}, fields=["customer"])
	if customers:

		for customer in customers:
			mandates = frappe.get_all("Sepa Mandate", filters={"customer": customer.customer, "registered_on_gocardless": 1})
			if mandates:
				for mandate in mandates:
					try:
						result = provider.get_single_mandate(mandate.name)
						frappe.db.set_value("Sepa Mandate", mandate.name, "status",\
							result.status.replace("_", " ").capitalize())
					except Exception as e:
						frappe.log_error(str(e), _("Sepa mandate status update error"))

def check_payment_status(provider):
	pending_requests = frappe.get_all("Integration Request",\
		filters={"integration_request_service": "GoCardless",\
		"status": ["in", ["Pending", "Queued"]]}, fields=["name", "service_document", "service_id"])

	if pending_requests:
		for request in pending_requests:
			if request["service_id"]:
				payments = []
				if request["service_document"] == "payment":
					gocardless_payments = provider.get_payments_on_gocardless(id=request["service_id"])
				elif request["service_document"] in ["mandates", "customer"]:
					map = {"mandates": "mandate", "customer": "customer"}
					gocardless_payments = provider.get_payments_on_gocardless(params={map.get(request["service_document"]): request["service_id"]})

				if gocardless_payments:
					payments.append(gocardless_payments)

				for payment in payments:
					if payment.status.replace("_", " ").capitalize() \
						!= frappe.db.get_value("Integration Request", request["name"], "service_status"):
						frappe.db.set_value("Integration Request", request["name"],\
							"service_status", payment.status.replace("_", " ").capitalize())

					if payment.status == "confirmed" or payment.status == "paid_out":
						frappe.db.set_value("Integration Request", request["name"], "status", "Completed")

def fetch_existing_payments(provider):
	existing_requests = [x["service_id"] for x in frappe.get_all("Integration Request",\
		filters={"integration_request_service": "GoCardless"}, fields=["service_id"])]
	payments = provider.get_payments_on_gocardless(params={"charge_date[gte]": nowdate()})

	for payment in payments:
		if payment.id not in existing_requests:
			missing_request = frappe.get_doc({
				"doctype": "Integration Request",
				"integration_type": "Request",
				"integration_request_service": "GoCardless",
				"payment_gateway_controller": provider.name,
				"data": str(payment.__dict__),
				"service_document": "payment",
				"service_id": payment.id,
				"service_status": payment.status,
				"status": "Confirmed" if (payment.status == "confirmed" or payment.status == "paid_out") else "Pending"
			}).insert(ignore_permissions=True)

def handle_webhooks(**kwargs):
	integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))

	if integration_request.get("service_document") == "mandates":
		GoCardlessMandateWebhookHandler(**kwargs)
	elif integration_request.get("service_document") == "payments":
		GoCardlessPaymentWebhookHandler(**kwargs)
	else:
		integration_request.db_set("error", _("This type of event is not handled by dokos"))
		integration_request.update_status({}, "Not Handled")
