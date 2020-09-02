# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import gocardless_pro
from frappe import _
from urllib.parse import urlencode
from frappe.utils import get_url, call_hook_method, flt, cint, nowdate, get_last_day, add_days
from frappe.integrations.utils import PaymentGatewayController,\
	create_request_log, create_payment_gateway
from erpnext.erpnext_integrations.doctype.gocardless_settings.webhook_events import (GoCardlessMandateWebhookHandler,
	GoCardlessPaymentWebhookHandler)
from erpnext.erpnext_integrations.doctype.gocardless_settings.api import (GoCardlessPayments, GoCardlessMandates, GoCardlessCustomers)

class GoCardlessSettings(PaymentGatewayController):
	supported_currencies = ["AUD", "CAD", "DKK", "EUR", "GBP", "NZD", "SEK", "USD"]

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
				access_token=self.get_password(fieldname="access_token", raise_exception=False),
				environment=self.environment
				)
			return self.client
		except Exception as e:
			frappe.throw(str(e))

	def on_update(self):
		create_payment_gateway('GoCardless-' + self.gateway_name, settings='GoCardLess Settings', controller=self.gateway_name)
		call_hook_method('payment_gateway_enabled', gateway='GoCardless-' + self.gateway_name)

	def on_payment_request_submission(self, payment_request):
		try:
			return self.check_mandate_validity(payment_request.get_customer())
		except Exception:
			frappe.log_error(frappe.get_traceback(), _("Sepa mandate validation failed for {0}".format(data.get("payer_name"))))

	def immediate_payment_processing(self, payment_request):
		try:
			processed_data = dict(
				amount=cint(flt(payment_request.grand_total, payment_request.precision("grand_total")) * 100),
				currency=payment_request.currency,
				description=payment_request.subject,
				reference=payment_request.reference_name,
				links={},
				metadata={
					"reference_doctype": payment_request.reference_doctype,
					"reference_name": payment_request.reference_name,
					"payment_request": payment_request.name
				}
			)

			customer = payment_request.get_customer()
			valid_mandate = self.check_mandate_validity(customer)
			if valid_mandate:
				processed_data["links"] = valid_mandate

				return GoCardlessPayments(self, payment_request).create(**processed_data)

		except Exception:
			frappe.log_error(frappe.get_traceback(),\
				_("GoCardless direct processing failed for {0}".format(data.reference_name)))

	def check_mandate_validity(self, customer):
		if frappe.db.exists("Sepa Mandate", dict(
			customer=customer,
			status=["not in", ["Cancelled", "Expired", "Failed"]]
			)
		):
			registered_mandate = frappe.db.get_value("Sepa Mandate", dict(
				customer=customer,
				status=["not in", ["Cancelled", "Expired", "Failed"]]
			), 'mandate')
			mandate = GoCardlessMandates(self).get(registered_mandate)

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
<<<<<<< HEAD
		payment_key = {"key": kwargs.get("payment_key")}
		return get_url("./integrations/gocardless_checkout?{0}".format(urlencode(kwargs) if not kwargs.get("payment_key") else urlencode(payment_key)))

	def handle_redirect_flow(self, redirect_flow, payment_request):
		customer = payment_request.get_customer()
		GoCardlessMandates(self).register(
			redirect_flow.links.mandate,
			customer
		)
=======
		return get_url("./integrations/gocardless_checkout?{0}".format(urlencode(kwargs)))

	def create_payment_request(self, data):
		self.data = frappe._dict(data)

		try:
			self.integration_request = create_request_log(self.data, "Request", "GoCardless")
			self._payment_request = frappe.get_doc("Payment Request", self.data.reference_docname)
			self.reference_document = self._payment_request

			self.create_charge_on_gocardless()
			return self.finalize_request(self.output.attributes.get("id") if self.output.attributes else None)

		except Exception as e:
			self.change_integration_request_status("Failed", "error", str(e))
			return self.error_message(402, _("GoCardless payment creation error"))

	def create_charge_on_gocardless(self):
		try:
			self.output = self.create_payment_on_gocardless()
			return self.process_output()
		except Exception as e:
			self.change_integration_request_status("Failed", "error", str(e))
			return self.error_message(402, _("GoCardless Payment Error"))

	def get_payments_on_gocardless(self, id=None, params=None):
		return self.get_payment_by_id(id) if id else self.get_payment_list(params)

	def get_payment_by_id(self, id):
		return self.client.payments.get(id)

	def get_payment_list(self, params=None):
		return self.client.payments.list(params=params).records

	def get_payout_by_id(self, id):
		return self.client.payouts.get(id)

	def get_payout_items_list(self, params):
		return self.client.payout_items.list(params=params).records

	def update_subscription(self, id, params=None):
		return self.client.subscriptions.update(id, params=params)

	def cancel_subscription(self, **kwargs):
		return self.client.subscriptions.cancel(kwargs.get("subscription"))

	def get_single_mandate(self, id):
		return self.client.mandates.get(id)

	@staticmethod
	def get_base_amount(payout_items, gocardless_payment):
		paid_amount = [x.amount for x in payout_items if (x.type == "payment_paid_out" and getattr(x.links, "payment") == gocardless_payment)]
		total = 0
		for p in paid_amount:
			total += flt(p)
		return total / 100

	@staticmethod
	def get_fee_amount(payout_items, gocardless_payment):
		fee_amount = [x.amount for x in payout_items if ((x.type == "gocardless_fee" or x.type == "app_fee") and getattr(x.links, "payment") == gocardless_payment)]
		total = 0
		for p in fee_amount:
			total += flt(p)
		return total / 100
>>>>>>> c967f3a40acc1140c04fdf7ccb5fa9ab4af284c9

		GoCardlessCustomers(self).register(
			redirect_flow.links.customer,
			customer
		)

		GoCardlessPayments(self, payment_request).create(
			amount=cint(payment_request.grand_total * 100),
			currency=payment_request.currency,
			description=payment_request.subject,
			reference=payment_request.reference_name,
			links={
				"mandate": redirect_flow.links.mandate
			},
			metadata={
				"reference_doctype": payment_request.reference_doctype,
				"reference_name": payment_request.reference_name,
				"payment_request": payment_request.name
			}
		)

	def update_subscription_gateway(self):
		if hasattr(self._payment_request, 'is_linked_to_a_subscription') and self._payment_request.is_linked_to_a_subscription():
			subscription = self._payment_request.is_linked_to_a_subscription()
			if frappe.db.exists("Subscription", subscription) \
				and (frappe.db.get_value("Subscription", subscription, "payment_gateway") != self._payment_request.payment_gateway):
				frappe.db.set_value("Subscription", subscription, "payment_gateway", self._payment_request.payment_gateway)

def handle_webhooks(**kwargs):
	from erpnext.erpnext_integrations.webhooks_controller import handle_webhooks as _handle_webhooks

	WEBHOOK_HANDLERS = {
		"mandates": GoCardlessMandateWebhookHandler,
		"payments": GoCardlessPaymentWebhookHandler
	}

	_handle_webhooks(WEBHOOK_HANDLERS, **kwargs)