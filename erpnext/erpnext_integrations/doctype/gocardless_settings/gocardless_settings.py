# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt


from urllib.parse import urlencode

import frappe
import gocardless_pro
from frappe import _
from frappe.utils import call_hook_method, cint, flt, get_url
from gocardless_pro import errors
from payments.utils.utils import PaymentGatewayController

from erpnext.erpnext_integrations.doctype.gocardless_settings.api import (
	GoCardlessCustomers,
	GoCardlessMandates,
	GoCardlessPayments,
	GoCardlessPayoutItems,
	GoCardlessPayouts,
)
from erpnext.erpnext_integrations.doctype.gocardless_settings.webhook_events import (
	GoCardlessWebhookHandler,
)
from erpnext.utilities import payment_app_import_guard


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
		with payment_app_import_guard():
			from payments.utils import create_payment_gateway

		create_payment_gateway(
			"GoCardless-" + self.gateway_name, settings="GoCardLess Settings", controller=self.gateway_name
		)
		call_hook_method("payment_gateway_enabled", gateway="GoCardless-" + self.gateway_name)

	def immediate_payment_processing(
		self, reference, customer, amount, currency, description, metadata
	):
		try:
			processed_data = dict(
				amount=round(flt(amount) * 100.0),
				currency=currency,
				description=description,
				reference=reference,
				links={},
				metadata=metadata,
			)

			valid_mandate = self.check_mandate_validity(customer)
			if valid_mandate.get("mandate"):
				processed_data["links"] = valid_mandate

				return getattr(GoCardlessPayments(self, reference).create(**processed_data), "id", None)
			else:
				frappe.throw(_("This customer has no valid mandate"))

		except Exception:
			self.log_error(
				_("GoCardless direct processing failed for {0}".format(reference)),
			)

	def check_mandate_validity(self, customer=None):
		if customer and frappe.db.exists(
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
		return get_url("./integrations/gocardless_checkout?{0}".format(urlencode(kwargs)))

	def handle_redirect_flow(self, redirect_flow, reference_document):
		customer = reference_document.get("customer") or reference_document.get_customer()
		if not customer:
			return

		GoCardlessMandates(self).register(redirect_flow.links.mandate, customer)

		GoCardlessCustomers(self).register(redirect_flow.links.customer, customer)

		payment = GoCardlessPayments(self, reference_document.name).create(
			amount=cint((reference_document.get("grand_total") or reference_document.get("amount")) * 100),
			currency=reference_document.get("currency"),
			description=reference_document.get("subject") or reference_document.get("description"),
			reference=reference_document.name,
			links={"mandate": redirect_flow.links.mandate},
			metadata={
				"reference_doctype": reference_document.doctype,
				"reference_name": reference_document.name,
			},
		)

		return getattr(payment, "id")

	def get_transaction_fees(self, payments):
		gc_payments = GoCardlessPayments(self).get(payments)
		gc_payment_links = getattr(gc_payments, "links", {})
		gc_payout = getattr(gc_payment_links, "payout")
		payout_items = GoCardlessPayoutItems(self).get_list(gc_payout)

		return frappe._dict(
			base_amount=self.get_base_amount(payout_items.records, gc_payments),
			fee_amount=self.get_fee_amount(payout_items.records, gc_payments),
			tax_amount=self.get_tax_amount(payout_items.records, gc_payments),
			exchange_rate=self.get_exchange_rate(GoCardlessPayouts(self).get(gc_payout)),
		)

	@staticmethod
	def get_base_amount(payout_items, payments):
		paid_amount = sum(
			[
				flt(x.amount)
				for x in payout_items
				if (x.type == "payment_paid_out" and getattr(x.links, "payment") == payments)
			]
		)
		return paid_amount / 100

	@staticmethod
	def get_fee_amount(payout_items, payments):
		fee_amount = sum(
			[
				flt(x.amount)
				for x in payout_items
				if (
					(x.type == "gocardless_fee" or x.type == "app_fee")
					and getattr(x.links, "payment") == payments
				)
			]
		)
		return fee_amount / 100

	@staticmethod
	def get_tax_amount(payout_items, payments):
		taxes = []
		for x in payout_items:
			if (x.type == "gocardless_fee" or x.type == "app_fee") and getattr(
				x.links, "payment"
			) == payments:
				taxes.extend(x.taxes)

		return sum([flt(x.get("amount")) for x in taxes]) / 100

	@staticmethod
	def get_exchange_rate(payout):
		return flt(getattr(payout.fx, "exchange_rate", 1) or 1)


def handle_webhooks(**kwargs):
	integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))

	if integration_request.service_document in ["mandates", "payments"]:
		GoCardlessWebhookHandler(**kwargs)
	else:
		integration_request.handle_failure(
			{"message": _("This type of event is not handled")}, "Not Handled"
		)
