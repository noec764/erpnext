# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import warnings
import frappe
from frappe import _
from urllib.parse import urlencode
from frappe.utils import get_url, call_hook_method, cint, flt
from frappe.integrations.utils import PaymentGatewayController, create_request_log, create_payment_gateway
from erpnext.erpnext_integrations.doctype.stripe_settings.webhook_events import (StripeChargeWebhookHandler, 
	StripePaymentIntentWebhookHandler, StripeInvoiceWebhookHandler)
import stripe
import json

class StripeSettings(PaymentGatewayController):
	currency_wise_minimum_charge_amount = {
		'JPY': 50, 'MXN': 10, 'DKK': 2.50, 'HKD': 4.00, 'NOK': 3.00, 'SEK': 3.00,
		'USD': 0.50, 'AUD': 0.50, 'BRL': 0.50, 'CAD': 0.50, 'CHF': 0.50, 'EUR': 0.50,
		'GBP': 0.30, 'NZD': 0.50, 'SGD': 0.50
	}

	def __init__(self, *args, **kwargs):
		super(StripeSettings, self).__init__(*args, **kwargs)
		if not self.is_new():
			self.configure_stripe()

	def configure_stripe(self):
		self.stripe = stripe
		self.stripe.api_key = self.get_password(fieldname="secret_key", raise_exception=False)
		self.stripe.default_http_client = stripe.http_client.RequestsClient()

	def get_supported_currencies(self):
		account = self.stripe.Account.retrieve()
		supported_payment_currencies = self.stripe.CountrySpec.retrieve(account["country"])[
			"supported_payment_currencies"
		]

		return [currency.upper() for currency in supported_payment_currencies]

	def on_update(self):
		create_payment_gateway('Stripe-' + self.gateway_name, settings='Stripe Settings', controller=self.gateway_name)
		call_hook_method('payment_gateway_enabled', gateway='Stripe-' + self.gateway_name)
		if not self.flags.ignore_mandatory:
			self.validate_stripe_credentials()

	def validate_stripe_credentials(self):
		try:
			self.configure_stripe()
			balance = self.stripe.Balance.retrieve()
			return balance
		except Exception as e:
			frappe.throw(_("Stripe connection could not be initialized.<br>Error: {0}").format(str(e)))

	def validate_transaction_currency(self, currency):
		if currency not in self.get_supported_currencies():
			frappe.throw(_("Please select another payment method. Stripe does not support transactions in currency '{0}'").format(currency))

	def validate_minimum_transaction_amount(self, currency, amount):
		if currency in self.currency_wise_minimum_charge_amount:
			if flt(amount) < self.currency_wise_minimum_charge_amount.get(currency, 0.0):
				frappe.throw(_("For currency {0}, the minimum transaction amount should be {1}").format(currency,
					self.currency_wise_minimum_charge_amount.get(currency, 0.0)))

	#TODO: Refactor
	def validate_subscription_plan(self, currency, plan):
		try:
			stripe_plan = self.stripe.Plan.retrieve(plan)

			if not stripe_plan.active:
				frappe.throw(_("Payment plan {0} is no longer active.").format(plan))
			if not currency == stripe_plan.currency.upper():
				frappe.throw(_("Payment plan {0} is in currency {1}, not {2}.")\
					.format(plan, stripe_plan.currency.upper(), currency))
			return stripe_plan
		except stripe.error.InvalidRequestError as e:
			frappe.throw(_("Invalid Stripe plan or currency: {0} - {1}").format(plan, currency))

	def get_payment_url(self, **kwargs):
		payment_key = {"key": kwargs.get("payment_key")}
		return get_url("./integrations/stripe_checkout?{0}".format(urlencode(kwargs) if not kwargs.get("payment_key") else urlencode(payment_key)))

	def cancel_subscription(self, **kwargs):
		from erpnext.erpnext_integrations.doctype.stripe_settings.api import StripeSubscription
		return StripeSubscription(self).cancel(
			kwargs.get("subscription"),
			invoice_now=kwargs.get("invoice_now", False),
			prorate=kwargs.get("prorate", False)
		)

def handle_webhooks(**kwargs):
	integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))

	WEBHOOK_HANDLERS = {
		"charge": StripeChargeWebhookHandler,
		"payment_intent": StripePaymentIntentWebhookHandler,
		"invoice": StripeInvoiceWebhookHandler
	}

	if WEBHOOK_HANDLERS.get(integration_request.get("service_document")):
		WEBHOOK_HANDLERS.get(integration_request.get("service_document"))(**kwargs)
	else:
		integration_request.db_set("error", _("This type of event is not handled by dokos"))
		integration_request.update_status({}, "Not Handled")
