# Copyright (c) 2021, Dokos SAS and contributors
# License: MIT. See LICENSE

from functools import cached_property

import frappe
from frappe import _
from frappe.model.document import Document


def is_desk() -> bool:
	try:
		path = frappe.request.path
		if path.startswith("/app/") or path.startswith("/api/"):
			return True
	except Exception:
		pass
	return False


class DuplicateRegistration(frappe.ValidationError):
	"""Raised when a duplicate registration is found for the same user (or email address if user is missing)."""

	@classmethod
	def throw(cls, registration: "EventRegistration | None" = None):
		if is_desk():
			return cls.throw_desk(registration)
		return cls.throw_website(registration)

	@classmethod
	def throw_desk(cls, registration: "EventRegistration | None" = None):
		frappe.throw(_("User is already registered for this event."), cls)

	@classmethod
	def throw_website(cls, registration: "EventRegistration | None" = None):
		if not (registration and registration.event):
			return cls.throw_desk()
		event_route = frappe.get_cached_value("Event", registration.event, "route")
		msg = _(
			"You have already registered for this event. You can cancel your registration on the event page: {0}"
		)
		link = f'<a href="/{event_route}">{event_route}</a>'
		msg = msg.format(link)
		frappe.throw(msg, cls)


class DuplicateRegistrationEmail(DuplicateRegistration):
	"""Raised when a duplicate registration is found for the same email address."""

	@classmethod
	def throw_website(cls, registration):
		frappe.throw(_("A registration with the same email address already exists."), cls)


class CannotDeletePaidRegistration(frappe.ValidationError):
	@classmethod
	def throw(cls, registration: "EventRegistration"):
		frappe.throw(_("Cannot delete paid registration: {0}").format(registration.name), cls)


class EventRegistration(Document):
	name: str
	event: str | None
	contact: str | None
	amount: float
	payment_status: str
	email: str | None
	first_name: str | None
	last_name: str | None

	@cached_property
	def event_doc(self):
		return frappe.get_doc("Event", self.event)

	def validate(self):
		self.validate_duplicates()
		self.validate_available_capacity_of_event()

		self.create_or_link_with_contact()
		if not self.contact and self.get_payment_amount() > 0:
			frappe.throw("A contact is required to register for paid events")

	def on_submit(self):
		self.add_contact_to_event()

	def on_cancel(self):
		# Prevent cancellation propagation to linked Sales Invoice.
		self.ignore_linked_doctypes = ["Sales Invoice"]
		self.remove_contact_from_event()

	def on_trash(self):
		if self.amount and self.payment_status == "Paid" and self.docstatus != 2:
			CannotDeletePaidRegistration.throw(self)

	def validate_duplicates(self):
		if self.allow_multiple_registrations_for_same_user():
			# Allow one User to register multiple times (for example, for different members of a same family).
			# Allow desk System Users to register some people multiple times.
			return

		base_filters = {"event": self.event, "name": ("!=", self.name), "docstatus": 1}
		if frappe.db.exists(
			"Event Registration",
			{"email": self.email, **base_filters},
		):
			DuplicateRegistrationEmail.throw(self)

		if self.user and frappe.db.exists(
			"Event Registration",
			{"user": self.user, **base_filters},
		):
			DuplicateRegistration.throw(self)

	def allow_multiple_registrations_for_same_user(self):
		# Use get_value because field might not exist.
		if not self.event_doc.allow_registrations:
			return False
		if not self.event_doc.get("allow_multiple_registrations", False):
			return False
		return True

	def validate_available_capacity_of_event(self):
		if self.docstatus == 1:
			remaining_capacity = self.get_event_remaining_capacity()
			if remaining_capacity <= 0:
				from erpnext.venue.doctype.event_registration.event.event import EventIsFull

				EventIsFull.throw()

	def get_event_remaining_capacity(self):
		event_info = frappe.db.get_value(
			"Event", self.event, ["allow_registrations", "max_number_of_registrations"], as_dict=True
		)
		max_number_of_registrations = int(event_info["max_number_of_registrations"] or 0)
		max_number_of_registrations = int(event_info["max_number_of_registrations"] or 0)

		if not event_info["allow_registrations"]:  # no limit
			return float("inf")
		if not max_number_of_registrations:  # no limit
			return float("inf")

		from pypika import functions as fn

		ER = frappe.qb.DocType("Event Registration")
		return max_number_of_registrations - int(
			frappe.qb.select(fn.Count(ER.star))
			.from_(ER)
			.where((ER.name != self.name) & (ER.event == self.event) & (ER.docstatus == 1))
			.run()[0][0]
		)

	def set_company_from_cart_settings(self):
		if self.meta.has_field("company"):
			from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import (
				get_shopping_cart_settings,
			)

			self.company = get_shopping_cart_settings().company

	def create_or_link_with_contact(self):
		contact = self.contact
		if not contact and self.email:
			contact = frappe.db.get_value("Contact", dict(email_id=self.email))

		if not contact and self.user:
			contact = frappe.db.get_value("Contact", dict(user=self.user))

		if not contact and self.email:
			contact_doc = frappe.get_doc(
				{
					"doctype": "Contact",
					"first_name": self.first_name,
					"last_name": self.last_name,
					"user": self.user,
				}
			)
			contact_doc.add_email(self.email, is_primary=1)
			contact_doc.insert(ignore_permissions=True)
			contact = contact_doc.name

		self.contact = contact

	def add_contact_to_event(self):
		if not self.contact:
			return
		event = frappe.get_doc("Event", self.event)
		event.add_participant(self.contact)
		event.save(ignore_permissions=True)

	def remove_contact_from_event(self):
		if not self.contact:
			return
		event = frappe.get_doc("Event", self.event)
		event.remove_participant(self.contact)
		event.save(ignore_permissions=True)

	def on_payment_authorized(self, status: str, reference_no: str = None):
		# Draft, Initiated, Pending, Paid, Failed, Cancelled, Completed
		new_status = status
		curr_status = self.payment_status or "Unpaid"  # Probably created from the desk

		if self.get_payment_amount() <= 0:
			self.db_set("payment_status", new_status)
			frappe.log_error(
				message=f"A payment for {self!r} was received with status {new_status!r} (ref_no: {reference_no}) but the payment amount is zero (or negative)",
			)
			return

		PAID_STATUSES = ("Authorized", "Completed", "Paid")
		if new_status in PAID_STATUSES and curr_status in ("Unpaid", "Pending"):
			self.flags.ignore_permissions = True
			self.db_set(
				"payment_status", "Paid", commit=True
			)  # Commit because we this is a change we don't want to lose
			self.submit()

			if not self.payment_gateway:
				frappe.throw(_("Missing Payment Gateway"))
			if not reference_no:
				frappe.throw(_("Missing Reference Number"))

			invoice = self.make_and_submit_invoice()
			self.make_payment_entry(
				reference_no=reference_no, payment_gateway=self.payment_gateway, invoice_doc=invoice
			)
		elif new_status in ("Failed", "Cancelled"):
			self.set("payment_status", new_status)
			self.cancel()
		elif new_status == "Pending" and curr_status == "Unpaid":
			self.set("payment_status", new_status)
			self.flags.ignore_permissions = True
			self.save()

	def on_webform_save(self, webform):
		# The document is created from the Web Form, it means that someone wants to register
		self.user = self.user or frappe.session.user
		self.set_company_from_cart_settings()

		if not self.flags.in_payment_webform:
			# Free registration
			self.payment_status = ""
			self.submit()  # Automatically submit when created from a Web Form.
		else:
			self.amount = self.get_payment_amount()
			self.payment_status = "Unpaid"
			self.save()

	def get_payment_amount(self) -> float:
		"""This is a PURE function that returns the amount to be paid (INCLUDING taxes) for the Event Registration.
		This function should not depend on the value of the `amount` field unless it returns it unchanged.

		In other words, the following code should guarantee `amt1 == amt2`:
		```python
		amt1 = self.amount = self.get_payment_amount()
		amt2 = self.amount = self.get_payment_amount()
		```
		"""
		# TODO: Fetch from item instead
		return self.amount

	def get_item_code(self):
		"""Returns the item_code of the Item used for the invoicing.
		The Item is fetched, in order, from the Event Registration, Event, Venue Settings.
		"""
		if item_code := self.get("item_code", None):
			return str(item_code)
		elif item_code := frappe.get_cached_value("Event", self.event, "registration_item_code"):
			return str(item_code)
		elif item_code := frappe.get_cached_value(
			"Venue Settings", "Venue Settings", "registration_item_code"
		):
			return str(item_code)
		frappe.throw(_("Item code not specified for Event Registration"))

	def get_or_make_customer(self) -> str:
		"""Returns the Customer associated with the Contact, creating it if needed."""
		contact_name = self.contact
		D = frappe.qb.DocType("Dynamic Link")
		res = (
			frappe.qb.from_(D)
			.select(D.link_name)
			.where((D.parenttype == "Contact") & (D.parent == contact_name) & (D.parentfield == "links"))
			.where(D.link_doctype == "Customer")
			.limit(1)
		).run()
		if res:
			return res[0][0]

		C = frappe.qb.DocType("Customer")
		res = (frappe.qb.from_(C).select(C.name).where(C.customer_name == contact_name).limit(1)).run()
		if res:
			return res[0][0]

		customer = self._make_and_link_to_new_customer()
		return customer.name

	def _make_and_link_to_new_customer(self):
		from erpnext.selling.doctype.customer.customer import make_customer_from_contact

		contact = frappe.get_doc("Contact", self.contact)
		contact.flags.ignore_permissions = True
		customer = make_customer_from_contact(contact, ignore_permissions=True)
		customer.update(
			{
				"customer_type": "Individual",
			}
		)
		customer.save()

		contact.append(
			"links",
			{
				"link_doctype": customer.doctype,
				"link_name": customer.name,
			},
		)
		contact.save()
		return customer

	from functools import cache

	@cache  # noqa
	def get_invoicing_details(self):
		company = None
		if self.meta.has_field("company"):
			# Get company from Registration, useful for multi-company mode
			company = self.get("company", None)
		if not company:
			# Else, get it from E Commerce Settings as a last resort
			from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import (
				get_shopping_cart_settings,
			)

			company = get_shopping_cart_settings().company

		currency = frappe.get_cached_value("Company", company, "default_currency")
		return frappe._dict(
			company=company,
			currency=currency,
			rate=self.get_payment_amount(),
			customer=self.get_or_make_customer(),
			item_code=self.get_item_code(),
		)

	def _set_fields_in_invoice(self, si: Document):
		details = self.get_invoicing_details()
		if details.rate <= 0:
			frappe.throw(_("Registration amount is zero but an invoice was requested."))
		si.update(
			{
				"doctype": "Sales Invoice",
				"company": details.company,
				"currency": details.currency,
				"customer": details.customer,
			}
		)
		si.append(
			"items",
			{
				"item_code": details.item_code,
				"qty": 1,
				"rate": details.rate,
				"event_registration": self.name,
			},
		)
		si.run_method("set_missing_values")
		si.run_method("calculate_taxes_and_totals")
		return si

	def make_and_submit_invoice(self):
		si = frappe.new_doc("Sales Invoice")
		si.flags.ignore_permissions = True
		self._set_fields_in_invoice(si)

		si.insert()
		si.submit()
		self.add_comment_about_document(si)

		return si

	def make_payment_entry(self, *, reference_no, payment_gateway, invoice_doc, mode_of_payment=None):
		# Imports
		from frappe.utils import nowdate

		from erpnext.accounts.doctype.payment_request.payment_request import (
			_get_payment_gateway_controller,
		)
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account

		# Check parameters
		if isinstance(payment_gateway, str):
			payment_gateway = frappe.get_doc("Payment Gateway", payment_gateway)

		if not payment_gateway:
			frappe.throw(_("Missing Payment Gateway"))

		# Invoicing and Payment data
		details = self.get_invoicing_details()
		base_amount = details.rate
		fee_amount = 0.0
		# exchange_rate = 1.0  # TODO

		mode_of_payment = mode_of_payment or payment_gateway.mode_of_payment

		# Update fee information if needed
		controller = _get_payment_gateway_controller(payment_gateway.name)
		if hasattr(controller, "get_transaction_fees"):
			fee_information = controller.get_transaction_fees(reference_no)
			base_amount = fee_information.base_amount
			fee_amount = fee_information.fee_amount
			# exchange_rate = fee_information.exchange_rate

		# Get destination account
		paid_to = get_bank_cash_account(mode_of_payment=mode_of_payment, company=details.company)
		if paid_to and "account" in paid_to:
			paid_to = paid_to["account"]

		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"party_type": "Customer",
				"party": details.customer,
				"company": details.company,
				# TODO: Handle exchange rates and currencies
				"paid_from_account_currency": details.currency,
				"paid_to_account_currency": details.currency,
				"source_exchange_rate": 1,
				"target_exchange_rate": 1,
				"reference_no": reference_no,
				"reference_date": nowdate(),
				"received_amount": base_amount - fee_amount,
				"paid_amount": base_amount - fee_amount,
				"mode_of_payment": mode_of_payment,
				"paid_to": paid_to,
			}
		)
		pe.append(
			"references",
			{
				"reference_doctype": invoice_doc.doctype,
				"reference_name": invoice_doc.name,
				"allocated_amount": base_amount,
			},
		)

		if fee_amount > 0.0:
			write_off_account, default_cost_center = frappe.get_cached_value(
				"Company", details.company, ["write_off_account", "cost_center"]
			)
			fee_account = payment_gateway.fee_account or write_off_account
			fee_cost_center = payment_gateway.cost_center or default_cost_center
			if fee_account and fee_cost_center:
				pe.append(
					"deductions",
					{
						"account": fee_account,
						"cost_center": fee_cost_center,
						"amount": fee_amount,
					},
				)

		pe.flags.ignore_permissions = True
		pe.insert()
		pe.submit()
		self.add_comment_about_document(pe)

		if fee_amount > 0.0 and not (payment_gateway.fee_account and payment_gateway.cost_center):
			# Add warning about fees not going into the right account/cost center.
			pe.add_comment(
				"Comment",
				_(
					"Payment Gateway '{0}' must have a Fee Account and Cost Center for the fees ({1}) to be correctly assigned."
				).format(payment_gateway.name, fee_amount),
				comment_email="Administrator",
			)

		return pe

	def add_comment_about_document(self, other_doc: Document):
		msg = _("{0}: {1}").format(_(other_doc.doctype), other_doc.name)
		html = f'<a href="{other_doc.get_url()}">{msg}</a>'
		self.add_comment("Comment", html, comment_email="Administrator")

	def get_linked_invoices(self):
		SII = frappe.qb.DocType("Sales Invoice Item")
		query = (
			frappe.qb.from_(SII)
			# Select the name(s) of the Sales Invoice(s)
			.select(SII.parent).distinct()
			# Use the row's creation time as a proxy for the invoice's creation time
			.orderby(SII.creation)
			# Is linked to this Event Registration
			.where(SII.event_registration == self.name)
			# Is an item of a Sales Invoice (superfluous check?)
			.where(SII.parenttype == "Sales Invoice")
		)
		res = [{"doctype": "Sales Invoice", "name": str(r[0])} for r in query.run()]
		return res


@frappe.whitelist()
def get_linked_invoices(name: str):
	doc: EventRegistration = frappe.get_doc("Event Registration", name)
	return doc.get_linked_invoices()


@frappe.whitelist()
def submit_then_make_invoice(source_name: str, target_doc=None):
	"""
	Create an unsaved Sales Invoice, set the Registration's payment_status to Paid and submit it.
	"""
	from frappe.model.mapper import get_mapped_doc

	def postprocess(registration: EventRegistration, invoice: Document):
		registration._set_fields_in_invoice(invoice)
		registration.set("payment_status", "Paid")
		registration.submit()

	return get_mapped_doc(
		"Event Registration",
		source_name,
		{
			"Event Registration": {
				"doctype": "Sales Invoice",
			}
		},
		postprocess=postprocess,
	)


@frappe.whitelist()
def mark_as_refunded(name: str):
	doc: EventRegistration = frappe.get_doc("Event Registration", name)
	if doc.docstatus == 2 and doc.payment_status == "Paid":
		doc.db_set("payment_status", "Refunded")


@frappe.whitelist()
def get_user_info():
	user = frappe.session.user

	if user == "Guest":
		return {}

	return frappe.db.get_value(
		"User", user, ["first_name", "last_name", "email", "mobile_no"], as_dict=True
	)


@frappe.whitelist(allow_guest=True)
def register_to_event(event, data):
	event = frappe.get_doc("Event", event)
	if not event.published:
		raise frappe.exceptions.PermissionError()
	if not event.allow_registrations:
		raise frappe.exceptions.PermissionError()
	if event.registration_form:  # Uses a custom Web Form, possibly paid
		frappe.throw("The simplified registration form is disabled for this event.")

	data = frappe.parse_json(data)

	user = None
	if user is None and frappe.session.user != "Guest":
		user = frappe.session.user

	if frappe.session.user == "Guest":
		if getattr(event, "disable_guest_registration", False):
			raise frappe.exceptions.PermissionError()

	try:
		doc = frappe.get_doc(
			{
				**data,
				"doctype": "Event Registration",
				"event": event.name,
				"user": user,
			}
		)

		doc.flags.ignore_permissions = True
		doc.submit()
		return doc
	except DuplicateRegistration:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Event registration error")
		frappe.clear_messages()
		raise


@frappe.whitelist()
def cancel_registration(event):
	user = frappe.session.user

	event = frappe.get_doc("Event", event)
	if not event.published:
		raise frappe.exceptions.PermissionError()
	if not event.allow_cancellations:
		raise frappe.exceptions.ValidationError()

	docname = frappe.get_value("Event Registration", dict(user=user, event=event, docstatus=1))
	if docname:
		doc = frappe.get_doc("Event Registration", docname)
		doc.flags.ignore_permissions = True
		doc.cancel()

	return docname


@frappe.whitelist()
def cancel_registration_by_name(name):
	user = frappe.session.user

	doc = frappe.get_doc("Event Registration", name)
	if doc.user != user:
		raise frappe.exceptions.PermissionError()

	event = frappe.get_doc("Event", doc.event)
	if not event.published:
		raise frappe.exceptions.PermissionError()
	if not event.allow_cancellations:
		raise frappe.exceptions.ValidationError()

	doc.flags.ignore_permissions = True

	if doc.docstatus == 0:
		doc.delete()
	elif doc.docstatus == 1:
		doc.cancel()
	elif doc.docstatus == 2:
		return
