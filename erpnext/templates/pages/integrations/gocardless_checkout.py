# Copyright (c) 2020, Dokos SAS and Contributors
# License: See license.txt

import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_default_contact
from payments.utils.utils import get_gateway_controller
from frappe.utils import fmt_money, get_url, check_format

expected_keys = (
	"amount",
	"title",
	"description",
	"reference_doctype",
	"reference_docname",
	"payer_name",
	"payer_email",
	"order_id",
	"currency",
)


def get_context(context):
	context.no_cache = 1

	if not (set(expected_keys) - set(list(frappe.form_dict))):
		for key in expected_keys:
			context[key] = frappe.form_dict[key]

		gateway_controller = get_gateway_controller(
			context.reference_doctype, context.reference_docname
		)
		if not gateway_controller:
			redirect_to_invalid_link()

		reference_document = frappe.get_doc(context.reference_doctype, context.reference_docname)
	else:
		print(set(expected_keys) - set(list(frappe.form_dict)))
		redirect_to_invalid_link()

	success_url = get_url(
		f"./integrations/gocardless_confirmation?reference_doctype={context.reference_doctype}&reference_docname={context.reference_docname}"
	)

	try:
		gocardless_settings = frappe.get_cached_doc("GoCardless Settings", gateway_controller)
		redirect_flow = gocardless_settings.client.redirect_flows.create(
			params={
				"description": _("Pay {0}").format(
					fmt_money(amount=context.amount, currency=context.currency)
				),
				"session_token": f"{context.reference_doctype}&{context.reference_docname}",
				"success_redirect_url": success_url,
				"prefilled_customer": PrefilledCustomer(reference_document, context).get(),
				"metadata": {
					"reference_doctype": context.reference_doctype,
					"reference_name": context.reference_docname
				},
			}
		)

		frappe.local.flags.redirect_location = redirect_flow.redirect_url
	except Exception:
		frappe.log_error(_("GoCardless Payment Error"))
		frappe.local.flags.redirect_location = "payment-failed"
		raise frappe.Redirect

	raise frappe.Redirect


def redirect_to_invalid_link():
	frappe.redirect_to_message(_("Invalid link"), _("This link is not valid.<br>Please contact us."))
	frappe.local.flags.redirect_location = frappe.local.response.location
	raise frappe.Redirect


class PrefilledCustomer:
	def __init__(self, reference_document, context):
		self.reference = reference_document
		self.context = context
		customer = self.reference.customer if hasattr(self.reference, 'customer') else self.reference.get("customer")
		self.customer = frappe.get_doc("Customer", customer)
		self.customer_address = {}
		self.primary_contact = {}

	def get(self):
		self.get_customer_address()
		self.get_primary_contact()
		email = self.primary_contact.get("email_id") or self.context.payer_email or frappe.session.user

		return {
			"company_name": self.customer.customer_name,
			"given_name": self.primary_contact.get("first_name") or "",
			"family_name": self.primary_contact.get("last_name") or "",
			"email": email if check_format(email) else "",
			"address_line1": self.customer_address.address_line1 or "",
			"address_line2": self.customer_address.address_line2 or "",
			"city": self.customer_address.city or "",
			"postal_code": self.customer_address.pincode or "",
			"country_code": frappe.db.get_value("Country", self.customer_address.country, "code") or "",
		}

	def get_customer_address(self):
		customer_address_name = None
		if self.reference.doctype == "Subscription":
			customer_address_name = frappe.db.get_value(
				"Customer", self.customer.name, "customer_primary_address"
			)
		else:
			customer_address_name = self.reference.get("customer_address")

		self.customer_address = (
			frappe.get_doc("Address", customer_address_name) if customer_address_name else frappe._dict()
		)

	def get_primary_contact(self):
		if self.customer.customer_primary_contact:
			self.primary_contact = frappe.db.get_value(
				"Contact",
				self.customer.customer_primary_contact,
				["first_name", "last_name", "email_id"],
				as_dict=True,
			)
		else:
			get_default_contact(self.customer.doctype, self.customer.name)
