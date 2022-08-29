# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt


from urllib.parse import urlencode

import frappe
import gocardless_pro
from frappe import _
from frappe.integrations.utils import PaymentGatewayController
from frappe.utils import call_hook_method, cint, flt, get_url
from gocardless_pro import errors
from payments.utils import create_payment_gateway

from erpnext.erpnext_integrations.doctype.gocardless_settings.api import (
	GoCardlessCustomers,
	GoCardlessMandates,
	GoCardlessPayments,
)
from erpnext.erpnext_integrations.doctype.gocardless_settings.webhook_events import (
	GoCardlessMandateWebhookHandler,
	GoCardlessPaymentWebhookHandler,
)


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
				environment=self.environment,
			)
			return self.client
		except Exception as e:
			frappe.throw(str(e))

	def on_update(self):
		create_payment_gateway(
			"GoCardless-" + self.gateway_name, settings="GoCardLess Settings", controller=self.gateway_name
		)
		call_hook_method("payment_gateway_enabled", gateway="GoCardless-" + self.gateway_name)

	def can_make_immediate_payment(self, payment_request):
		return bool(self.check_mandate_validity(payment_request.get_customer(), {}).get("mandate"))

	def immediate_payment_processing(self, payment_request):
		if not self.can_make_immediate_payment(payment_request):
			return

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
					"payment_request": payment_request.name,
				},
			)

			customer = payment_request.get_customer()
			valid_mandate = self.check_mandate_validity(customer)
			if valid_mandate.get("mandate"):
				processed_data["links"] = valid_mandate

				return getattr(GoCardlessPayments(self, payment_request).create(**processed_data), "id", None)
			else:
				frappe.throw(_("This customer has no valid mandate"))

		except Exception:
			self.log_error(
				_("GoCardless direct processing failed for {0}".format(payment_request.name)),
			)

	def check_mandate_validity(self, customer):
		if frappe.db.exists(
			"Sepa Mandate", dict(customer=customer, status=["not in", ["Cancelled", "Expired", "Failed"]])
		):
			registered_mandate = frappe.db.get_value(
				"Sepa Mandate",
				dict(customer=customer, status=["not in", ["Cancelled", "Expired", "Failed"]]),
				"mandate",
			)

			try:
				mandate = GoCardlessMandates(self).get(registered_mandate)

				if (
					mandate.status == "pending_customer_approval"
					or mandate.status == "pending_submission"
					or mandate.status == "submitted"
					or mandate.status == "active"
				):
					return {"mandate": registered_mandate}
			except errors.InvalidApiUsageError:
				pass
		return {}

	def get_environment(self):
		return "sandbox" if self.use_sandbox else "live"

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(
				_(
					"Please select another payment method. GoCardless does not support transactions in currency '{0}'"
				).format(currency)
			)

	def get_payment_url(self, **kwargs):
		payment_key = {"key": kwargs.get("payment_key")}
		return get_url(
			"./integrations/gocardless_checkout?{0}".format(
				urlencode(kwargs) if not kwargs.get("payment_key") else urlencode(payment_key)
			)
		)

	def handle_redirect_flow(self, redirect_flow, payment_request):
		customer = payment_request.get_customer()
		if not customer:
			return
		GoCardlessMandates(self).register(redirect_flow.links.mandate, customer)

		GoCardlessCustomers(self).register(redirect_flow.links.customer, customer)

		GoCardlessPayments(self, payment_request).create(
			amount=cint(payment_request.grand_total * 100),
			currency=payment_request.currency,
			description=payment_request.subject,
			reference=payment_request.reference_name,
			links={"mandate": redirect_flow.links.mandate},
			metadata={
				"reference_doctype": payment_request.reference_doctype,
				"reference_name": payment_request.reference_name,
				"payment_request": payment_request.name,
			},
		)


def handle_webhooks(**kwargs):
	from erpnext.erpnext_integrations.webhooks_controller import handle_webhooks as _handle_webhooks

	WEBHOOK_HANDLERS = {
		"mandates": GoCardlessMandateWebhookHandler,
		"payments": GoCardlessPaymentWebhookHandler,
	}

	_handle_webhooks(WEBHOOK_HANDLERS, **kwargs)
