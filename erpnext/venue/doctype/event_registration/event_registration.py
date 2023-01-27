# Copyright (c) 2021, Dokos SAS and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class DuplicateRegistration(frappe.ValidationError):
	pass


class EventRegistration(Document):
	def validate(self):
		self.check_duplicates()
		self.validate_available_capacity_of_event()
		self.create_or_link_with_contact()

	def on_submit(self):
		self.add_contact_to_event()

	def on_cancel(self):
		self.remove_contact_from_event()

	def check_duplicates(self):
		if frappe.db.exists(
			"Event Registration",
			dict(email=self.email, event=self.event, name=("!=", self.name), docstatus=1),
		):
			frappe.throw(_("User is already registered for this event."), DuplicateRegistration)

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

	def on_payment_authorized(self, status_changed_to: str, reference_no: str):
		# Draft, Initiated, Pending, Paid, Failed, Cancelled, Completed
		if status_changed_to in ("Failed", "Cancelled"):
			self.cancel()
		if status_changed_to in ("Paid", "Completed"):
			self.submit()

	def on_webform_save(self, web_form: Document):
		self.user = frappe.session.user
		self.submit()  # Automatically submit when created from a Web Form.


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
