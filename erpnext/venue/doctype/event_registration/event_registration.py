# Copyright (c) 2021, Dokos SAS and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class DuplicateRegistration(frappe.ValidationError):
	@classmethod
	def throw(cls, registration: dict = None):
		if frappe.request.path.startswith("/app/") or frappe.request.path.startswith("/api/"):
			cls.throw_desk(registration)
		else:
			cls.throw_website(registration)

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

	def on_submit(self):
		self.add_contact_to_event()

	def on_cancel(self):
		# Prevent cancellation propagation to linked Sales Invoice.
		self.ignore_linked_doctypes = ["Sales Invoice"]
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

	def set_company_from_cart_settings(self):
		if self.meta.has_field("company"):
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
			self.db_set("payment_status", new_status)
			return

		if new_status == "Paid" and curr_status in ("Unpaid", "Pending"):
			self.flags.ignore_permissions = True
			self.db_set("payment_status", new_status, commit=True)
			self.submit()

			if not self.payment_gateway:
				frappe.throw(_("Missing Payment Gateway"))
			if not reference_no:
				frappe.throw(_("Missing Reference Number"))

			invoice = self.make_and_submit_invoice()
			self.make_payment_entry(reference_no=reference_no, payment_gateway=self.payment_gateway, invoice_doc=invoice)
		elif new_status in ("Failed", "Cancelled"):
			self.set("payment_status", new_status)
			self.cancel()

	def on_webform_save(self, web_form: Document):
		# The document is created from the Web Form, it means that someone wants to register
		self.user = frappe.session.user
		self.set_company_from_cart_settings()

		if self.get_payment_amount() <= 0:
			# Free registration
			self.payment_status = "Paid"
			self.submit()  # Automatically submit when created from a Web Form.
		else:
			self.payment_status = "Unpaid"
			self.save()

	def get_payment_amount(self) -> float:
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
		res = (
			frappe.qb.from_(C)
			.select(C.name)
			.where(C.customer_name == contact_name)
			.limit(1)
		).run()
		if res:
			return res[0][0]

		customer = self._make_and_link_to_new_customer()
		return customer.name

	def _make_and_link_to_new_customer(self):
		from erpnext.selling.doctype.customer.customer import make_customer_from_contact
		contact = frappe.get_doc("Contact", self.contact)
		customer = make_customer_from_contact(contact)
		customer.update({
			"customer_type": "Individual",
		})
		customer.save()

		contact.append("links", {
			"link_doctype": customer.doctype,
			"link_name": customer.name,
		})
		contact.save()
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
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
		from erpnext.accounts.doctype.payment_request.payment_request import _get_payment_gateway_controller
		from frappe.utils import nowdate

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
				"allocated_amount": base_amount
			}
		)

		if fee_amount > 0.0:
			write_off_account, default_cost_center = frappe.get_cached_value("Company", details.company, ["write_off_account", "cost_center"])
			fee_account = payment_gateway.fee_account or write_off_account
			fee_cost_center = payment_gateway.cost_center or default_cost_center
			if fee_account and fee_cost_center:
				pe.append("deductions", {
					"account": fee_account,
					"cost_center": fee_cost_center,
					"amount": fee_amount,
				})

		pe.flags.ignore_permissions = True
		pe.insert()
		pe.submit()
		self.add_comment_about_document(pe)

		if fee_amount > 0.0 and not (payment_gateway.fee_account and payment_gateway.cost_center):
			# Add warning about fees not going into the right account/cost center.
			pe.add_comment(
				"Comment",
				_("Payment Gateway '{0}' must have a Fee Account and Cost Center for the fees ({1}) to be correctly assigned.").format(payment_gateway.name, fee_amount),
				comment_email="Administrator",
			)

		return pe

	def add_comment_about_document(self, other_doc: Document):
		msg = _("{0}: {1}").format(_(other_doc.doctype), other_doc.name)
		html = f'<a href="{other_doc.get_url()}">{msg}</a>'
		self.add_comment("Comment", html, comment_email="Administrator")

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

	return get_mapped_doc("Event Registration", source_name, {
		"Event Registration": {
			"doctype": "Sales Invoice",
		}
	}, postprocess=postprocess)


@frappe.whitelist()
def mark_as_refunded(name: str):
	doc: EventRegistration = frappe.get_doc("Event Registration", name)
	if doc.docstatus == 2 and doc.payment_status == "Paid":
		doc.db_set("payment_status", "Refunded")


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

