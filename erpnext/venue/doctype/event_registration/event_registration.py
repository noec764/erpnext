# Copyright (c) 2021, Dokos SAS and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class DuplicateRegistration(frappe.ValidationError):
	@classmethod
	def throw(cls, registration: dict = None):
		if frappe.request.path.startswith("/app"):
			cls.throw_desk(self)
		else:
			cls.throw_website(self)

	@classmethod
	def throw_desk(cls, registration: dict = None):
		frappe.throw(_("User is already registered for this event."), cls)

	@classmethod
	def throw_website(cls, registration: dict = None):
		if not (registration and registration.event):
			return cls.throw_desk()
		event_route = frappe.get_cached_value("Event", registration.event, "route")
		msg = _("You have already registered for this event. You can cancel your registration on the event page: {0}")
		link = f'<a href="/{event_route}">{event_route}</a>'
		msg = msg.format(link)
		frappe.throw(msg, cls)

class CannotDeletePaidRegistration(frappe.ValidationError):
	@classmethod
	def throw(cls, registration: dict):
		frappe.throw(_("Cannot delete paid registration: {0}").format(registration.name), cls)

class EventRegistration(Document):
	def validate(self):
		self.check_duplicates()
		self.validate_available_capacity_of_event()
		self.create_or_link_with_contact()
		self.fill_company_field_if_needed()

	def on_submit(self):
		self.add_contact_to_event()

	def on_cancel(self):
		self.remove_contact_from_event()

	def on_trash(self):
		if self.amount and self.payment_status == "Paid" and self.docstatus != 2:
			CannotDeletePaidRegistration.throw(self)

	def check_duplicates(self):
		# TODO: Allow one User to register for different Contacts.
		if frappe.db.exists(
			"Event Registration",
			dict(email=self.email, event=self.event, name=("!=", self.name), docstatus=1),
		):
			DuplicateRegistration.throw(self)

	def validate_available_capacity_of_event(self):
		if self.docstatus == 1:
			remaining_capacity = self.get_event_remaining_capacity()
			if remaining_capacity <= 0:
				from frappe.desk.doctype.event.event import EventIsFull
				EventIsFull.throw()

	def get_event_remaining_capacity(self):
		event_info = frappe.db.get_value("Event", self.event, ["allow_registrations", "max_number_of_registrations"], as_dict=True)
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

	def fill_company_field_if_needed(self):
		if self.meta.has_field("company"):
			if not self.get("company", None):
				from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import get_shopping_cart_settings
				self.company = get_shopping_cart_settings().company

	def create_or_link_with_contact(self):
		contact = self.contact
		if not contact:
			contact = frappe.db.get_value("Contact", dict(email_id=self.email))

		if not contact and self.user:
			contact = frappe.db.get_value("Contact", dict(user=self.user))

		if not contact:
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
		event = frappe.get_doc("Event", self.event)
		event.add_participant(self.contact)
		event.save(ignore_permissions=True)

	def remove_contact_from_event(self):
		event = frappe.get_doc("Event", self.event)
		event.remove_participant(self.contact)
		event.save(ignore_permissions=True)

	def on_payment_authorized(self, status: str, reference_no: str = None):
		# Draft, Initiated, Pending, Paid, Failed, Cancelled, Completed
		new_status = status
		curr_status = self.payment_status or "Unpaid"  # Probably created from the desk

		if self.get_payment_amount() <= 0:
			return

		if new_status == "Paid" and curr_status in ("Unpaid", "Pending"):
			self.flags.ignore_permissions = True
			self.db_set("payment_status", new_status, commit=True)
			self.submit()

			if not self.payment_gateway:
				frappe.throw(_("Missing Payment Gateway"))
			if not reference_no:
				frappe.throw(_("Missing Reference Number"))

			self.make_invoice()
			self.make_payment_entry(reference_no=reference_no, payment_gateway=self.payment_gateway)
		elif new_status in ("Failed", "Cancelled"):
			self.cancel()

	def on_webform_save(self, web_form: Document):
		# The document is created from the Web Form, it means that someone wants to register
		self.user = frappe.session.user

		if self.get_payment_amount() <= 0:
			# Free registration
			self.payment_status = "Paid"
			self.submit()  # Automatically submit when created from a Web Form.
		else:
			self.payment_status = "Unpaid"
			self.save()

	def get_payment_amount(self):
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
		elif item_code := frappe.get_cached_value("Venue Settings", "Venue Settings", "registration_item_code"):
			return str(item_code)
		frappe.throw("Item code not specified for Event Registration")

	def get_or_make_customer(self) -> str:
		"""Returns the Customer associated with the Contact, creating it if needed."""
		contact_name = self.contact
		D = frappe.qb.DocType("Dynamic Link")
		query = (
			frappe.qb.from_(D)
			.select(D.link_name)
			.where((D.parenttype == "Contact") & (D.parent == contact_name) & (D.parentfield == "links"))
			.where(D.link_doctype == "Customer")
			.limit(1)
		)
		res = query.run()
		if len(res) == 0:
			customer = self._make_and_link_to_new_customer()
			return customer.name
		else:
			return res[0][0]

	def _make_and_link_to_new_customer(self):
		from erpnext.selling.doctype.customer.customer import make_customer_from_contact
		customer = make_customer_from_contact(frappe.get_doc("Contact", self.contact))
		customer.update({
			"customer_type": "Individual",
		})
		customer.save()

		self.append("links", {
			"link_doctype": customer.doctype,
			"link_name": customer.name,
		})
		self.save()
		return customer

	from functools import cache
	@cache
	def get_invoicing_details(self):
		company = None
		if self.meta.has_field("company"):
			# Get company from Registration, useful for multi-company mode
			company = self.get("company", None)
		if not company:
			# Else, get it from E Commerce Settings as a last resort
			from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import get_shopping_cart_settings
			company = get_shopping_cart_settings().company

		currency = frappe.get_cached_value("Company", company, "default_currency")
		return frappe._dict(
			company=company,
			currency=currency,
			rate=self.get_payment_amount(),
			customer=self.get_or_make_customer(),
			item_code=self.get_item_code(),
		)

	def make_invoice(self):
		details = self.get_invoicing_details()

		if details.rate <= 0:
			raise ValueError("Registration amount is zero but a payment was requested.")

		si = frappe.get_doc(
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
			},
		)

		si.flags.ignore_permissions = True
		si.insert()
		si.submit()

		return si

	def make_payment_entry(self, *, reference_no, payment_gateway=None, mode_of_payment=None):
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
		from frappe.utils import nowdate
		details = self.get_invoicing_details()

		if isinstance(payment_gateway, str):
			payment_gateway = frappe.get_doc("Payment Gateway", payment_gateway)
		if payment_gateway:
			mode_of_payment = payment_gateway.mode_of_payment

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
				"paid_from_account_currency": details.currency,
				"paid_to_account_currency": details.currency,
				"source_exchange_rate": 1,
				"target_exchange_rate": 1,
				"reference_no": reference_no,
				"reference_date": nowdate(),
				"received_amount": details.rate,
				"paid_amount": details.rate,
				"mode_of_payment": mode_of_payment,
				"paid_to": paid_to,
			}
		)
		pe.flags.ignore_permissions = True
		pe.insert()
		pe.submit()

		return pe


@frappe.whitelist()
def get_user_info(user=None):
	user = frappe.session.user

	if user == "Guest":
		return {}

	return frappe.db.get_value(
		"User", user, ["first_name", "last_name", "email", "mobile_no"], as_dict=True
	)



@frappe.whitelist(allow_guest=True)
def register_to_event(event, data, user=None):
	import warnings
	warnings.warn("API endpoint erpnext.[...].event_registration.register_to_event is deprecated in favor of Web Form")

	if frappe.session.user == "Guest":
		raise frappe.exceptions.PermissionError()

	user = frappe.session.user

	try:
		registration = frappe.get_doc(
			dict({"doctype": "Event Registration", "event": event, "user": user}, **frappe.parse_json(data))
		)

		registration.flags.ignore_permissions = True
		registration.flags.ignore_mandatory = True
		registration.submit()
		return registration
	except DuplicateRegistration:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Event registration error")
		frappe.clear_messages()


@frappe.whitelist()
def cancel_registration(event):
	user = frappe.session.user

	registration = frappe.get_value("Event Registration", dict(user=user, event=event, docstatus=1))

	if registration:
		doc = frappe.get_doc("Event Registration", registration)
		doc.flags.ignore_permissions = True
		doc.cancel()

	return registration


@frappe.whitelist()
def cancel_registration_by_name(name):
	user = frappe.session.user

	doc = frappe.get_doc("Event Registration", name)
	if doc.user != user:
		return

	doc.flags.ignore_permissions = True

	if doc.docstatus == 0:
		doc.delete()
	elif doc.docstatus == 1:
		doc.cancel()
	elif doc.docstatus == 2:
		return


@frappe.whitelist()
def mark_registration_as_refunded(name):
	doc = frappe.get_doc("Event Registration", name)
	if doc.docstatus == 2:
		if doc.payment_status == "Paid":
			doc.db_set("payment_status", "Refunded")
