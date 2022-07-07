# Copyright (c) 2022, Dokos SAS and Contributors
# License: GNU General Public License v3. See license.txt

from datetime import datetime

import frappe
from frappe import _
from frappe.integrations.utils import get_gateway_controller
from frappe.utils import cint, flt, fmt_money, get_datetime, getdate, nowdate

from erpnext.accounts.doctype.subscription.subscription_state_manager import SubscriptionPeriod
from erpnext.erpnext_integrations.doctype.stripe_settings.api import (
	StripeCustomer,
	StripeInvoice,
	StripePaymentIntent,
	StripePaymentMethod,
	StripeSubscription,
)

expected_keys = (
	"amount",
	"title",
	"description",
	"reference_doctype",
	"reference_docname",
	"webform",
	"payer_name",
	"payer_email",
	"order_id",
	"currency",
)


def get_context(context):
	context.no_cache = 1
	context.lang = frappe.local.lang

	if frappe.db.exists(
		"Payment Request", {"payment_key": frappe.form_dict.get("key"), "docstatus": 1}
	):
		payment_request = frappe.get_doc("Payment Request", {"payment_key": frappe.form_dict.get("key")})

		if payment_request.status in ("Paid", "Completed", "Cancelled"):
			frappe.redirect_to_message(
				_("Already paid"),
				_("This payment has already been done.<br>Please contact us if you have any question."),
			)
			frappe.local.flags.redirect_location = frappe.local.response.location
			raise frappe.Redirect

		gateway_controller = frappe.get_doc(
			"Stripe Settings", get_gateway_controller(payment_request.doctype, payment_request.name)
		)

		customer_id = payment_request.get_customer()
		context.customer = (
			StripeCustomer(gateway_controller).get_or_create(customer_id).get("id") if customer_id else ""
		)

		context.publishable_key = gateway_controller.publishable_key
		context.payment_key = frappe.form_dict.get("key")
		context.image = gateway_controller.header_img
		context.description = payment_request.subject
		context.payer_name = (
			frappe.db.get_value("Customer", customer_id, "customer_name") if customer_id else ""
		)
		context.payer_email = payment_request.email_to or (
			frappe.session.user if frappe.session.user != "Guest" else ""
		)
		context.amount = fmt_money(amount=payment_request.grand_total, currency=payment_request.currency)
		context.is_subscription = (
			1
			if (
				payment_request.is_linked_to_a_subscription()
				and cint(gateway_controller.subscription_cycle_on_stripe)
			)
			else 0
		)
		context.payment_success_redirect = gateway_controller.redirect_url or "payment-success"
		context.payment_failure_redirect = gateway_controller.failure_redirect_url or "payment-failed"

	elif not (set(expected_keys) - set(list(frappe.form_dict))):
		for key in expected_keys:
			context[key] = frappe.form_dict[key]

		gateway_controller = frappe.get_doc(
			"Stripe Settings", get_gateway_controller("Web Form", context.webform)
		)
		context.publishable_key = get_api_key(gateway_controller)
		context.image = gateway_controller.header_img
		context.is_subscription = 0
		context.payment_success_redirect = gateway_controller.redirect_url or "payment-success"
		context.payment_failure_redirect = gateway_controller.failure_redirect_url or "payment-failed"
		context.grand_total = context["amount"]
		context.amount = fmt_money(amount=context["amount"], currency=context["currency"])

	else:
		frappe.redirect_to_message(_("Invalid link"), _("This link is not valid.<br>Please contact us."))
		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect


def get_api_key(gateway_controller):
	if isinstance(gateway_controller, str):
		return frappe.get_doc("Stripe Settings", gateway_controller).publishable_key

	return gateway_controller.publishable_key


@frappe.whitelist(allow_guest=True)
def make_payment_intent(
	payment_key,
	customer=None,
	reference_doctype=None,
	reference_docname=None,
	webform=None,
	grand_total=None,
	currency=None,
):
	if frappe.db.exists("Payment Request", {"payment_key": payment_key}):
		payment_request = frappe.get_doc("Payment Request", {"payment_key": payment_key})
		gateway_controller_name = get_gateway_controller("Payment Request", payment_request.name)
		gateway_controller = frappe.get_doc("Stripe Settings", gateway_controller_name)

	elif webform and reference_doctype and reference_docname:
		gateway_controller_name = get_gateway_controller("Web Form", webform)
		gateway_controller = frappe.get_doc("Stripe Settings", gateway_controller_name)
		payment_request = create_payment_request(
			reference_doctype=reference_doctype,
			reference_name=reference_docname,
			grand_total=grand_total,
			currency=currency,
			payment_gateway=frappe.db.get_value("Web Form", webform, "payment_gateway"),
		)

	payment_intent_object = dict(
		metadata={
			"reference_doctype": payment_request.reference_doctype,
			"reference_name": payment_request.reference_name,
			"payment_request": payment_request.name,
		}
	)

	if not webform:
		payment_intent_object.update(dict(setup_future_usage="off_session"))

	if customer:
		payment_intent_object.update(dict(customer=customer))

	payment_intent = StripePaymentIntent(gateway_controller, payment_request).create(
		amount=cint(flt(payment_request.grand_total) * 100),
		currency=payment_request.currency,
		**payment_intent_object
	)

	return payment_intent


def create_payment_request(**kwargs):
	from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request

	return frappe.get_doc(
		make_payment_request(
			**{
				"dt": kwargs.get("reference_doctype"),
				"dn": kwargs.get("reference_name"),
				"grand_total": kwargs.get("grand_total"),
				"submit_doc": True,
				"return_doc": True,
				"mute_email": 1,
				"currency": kwargs.get("currency"),
				"payment_gateway": kwargs.get("payment_gateway"),
			}
		)
	)


@frappe.whitelist(allow_guest=True)
def retry_invoice(**kwargs):
	payment_request, payment_gateway = _update_payment_method(**kwargs)

	invoice = StripeInvoice(payment_gateway).retrieve(
		kwargs.get("invoiceId"), expand=["payment_intent"]
	)
	return invoice


@frappe.whitelist(allow_guest=True)
def make_subscription(**kwargs):
	payment_request, payment_gateway = _update_payment_method(**kwargs)

	subscription = frappe.get_doc("Subscription", payment_request.is_linked_to_a_subscription())
	items = [
		{"price": x.stripe_plan, "quantity": x.qty}
		for x in subscription.plans
		if x.stripe_plan and x.status == "Active"
	]

	data = dict(
		items=items,
		expand=["latest_invoice.payment_intent"],
		metadata={"reference_doctype": subscription.doctype, "reference_name": subscription.name},
	)

	if subscription.trial_period_end:
		data.update({"trial_end": int(datetime.timestamp(get_datetime(subscription.trial_period_end)))})

	if getdate(subscription.start) < getdate(nowdate()):
		data.update(
			{
				"backdate_start_date": int(datetime.timestamp(get_datetime(subscription.start))),
				"billing_cycle_anchor": int(
					datetime.timestamp(get_datetime(SubscriptionPeriod(subscription).get_next_invoice_date()))
				),
			}
		)
	else:
		data.update({"proration_behavior": "none"})

	return StripeSubscription(payment_gateway).create(
		subscription.name, kwargs.get("customerId"), **data
	)


def _update_payment_method(**kwargs):
	if not kwargs.get("payment_key"):
		return

	payment_request = frappe.get_doc("Payment Request", {"payment_key": kwargs.get("payment_key")})
	gateway_controller_name = get_gateway_controller("Payment Request", payment_request.name)
	gateway_controller = frappe.get_doc("Stripe Settings", gateway_controller_name)

	StripePaymentMethod(gateway_controller).attach(
		kwargs.get("paymentMethodId"), kwargs.get("customerId")
	)
	StripeCustomer(gateway_controller).update(
		kwargs.get("customerId"),
		invoice_settings={
			"default_payment_method": kwargs.get("paymentMethodId"),
		},
	)

	return payment_request, gateway_controller


@frappe.whitelist(allow_guest=True)
def update_payment_method(**kwargs):
	_update_payment_method(**kwargs)
