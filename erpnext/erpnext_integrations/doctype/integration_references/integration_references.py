# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from payments.payment_gateways.doctype.stripe_settings.api.customer import StripeCustomer

class IntegrationReferences(Document):
	pass

def can_make_immediate_payment(payment_request, controller):
	customer = payment_request.get_customer()
	if not customer:
		return

	if controller.doctype == "Stripe Settings":
		stripe_customer_id = frappe.db.get_value(
			"Integration References",
			dict(customer=customer, stripe_settings=controller.name),
			"stripe_customer_id",
		)

		if stripe_customer_id:
			stripe_customer = StripeCustomer(controller).get(stripe_customer_id)
			return bool(stripe_customer.get("default_source")) or bool(
				stripe_customer.get("invoice_settings", {}).get("default_payment_method")
			)

	elif controller.doctype == "GoCardless Settings":
		return bool(controller.check_mandate_validity(payment_request.get_customer()).get("mandate"))

