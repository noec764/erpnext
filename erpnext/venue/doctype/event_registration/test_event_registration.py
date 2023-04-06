# Copyright (c) 2021, Dokos SAS and Contributors
# License: MIT. See LICENSE


from contextlib import contextmanager

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.venue.doctype.event_registration.event_registration import (
	DuplicateRegistration,
	DuplicateRegistrationEmail,
	EventRegistration,
	cancel_registration_by_name,
	register_to_event,
)


@contextmanager
def with_user(user):
	"""Context manager to set user in the request"""
	original_user = frappe.session.user if frappe.session else None
	frappe.set_user(user)
	yield
	frappe.set_user(original_user)


def random_email():
	import random
	import string

	return "evreg+" + "".join(random.choice(string.ascii_letters) for i in range(10)) + "@example.com"


class TestEventRegistration(FrappeTestCase):
	@classmethod
	@with_user("Administrator")
	def setUpClass(cls):
		super().setUpClass()
		cls.event_free_cancellable = frappe.get_doc(
			{
				"subject": "Test Event (Free, Cancellable)",
				"starts_on": "2023-01-01 14:00:00",
				"ends_on": "2023-01-01 18:00:00",
				"event_category": "Event",
				"event_type": "Public",
				"status": "Open",
				"visible_for": "All",
				"published": 1,
				"allow_registrations": 1,
				"allow_cancellations": 1,
				"registration_amount": 0,
				"doctype": "Event",
			}
		).insert()

	@classmethod
	@with_user("Administrator")
	def tearDownClass(cls):
		super().tearDownClass()
		frappe.delete_doc("Event", cls.event_free_cancellable.name)

	def get_my_registrations(self):
		if frappe.session.user == "Guest":
			return frappe.get_all("Event Registration", filters={"user": ""})
		return frappe.get_all("Event Registration", filters={"user": frappe.session.user})

	def assertEventRegistration(self, name: str, event: str, data: dict):
		registration: EventRegistration = frappe.get_doc("Event Registration", name)

		self.assertEqual(registration.event, event)

		if frappe.session.user == "Guest":
			self.assertIsNone(registration.user)
		else:
			self.assertEqual(registration.user, frappe.session.user)

		for key, value in data.items():
			self.assertEqual(registration.get(key), value)

		return registration

	def cleanRegistrations(self, registrations: list[EventRegistration]):
		for registration in registrations:
			reg = frappe.get_doc("Event Registration", registration.name)
			reg.flags.ignore_permissions = True
			reg.cancel()
			reg.delete()

	@with_user("Guest")
	def test_api_guest_registration(self):
		data = {
			"email": random_email(),
			"first_name": "Lorem",
			"last_name": "EventRegistration",
		}
		register_to_event(self.event_free_cancellable.name, data)

		my_registrations = self.get_my_registrations()
		self.assertEqual(len(my_registrations), 1)
		self.assertEventRegistration(my_registrations[0].name, self.event_free_cancellable.name, data)
		self.cleanRegistrations(my_registrations)

	@with_user("Guest")
	def test_api_guest_registration_adversarial_1(self):
		with self.assertRaises(frappe.MandatoryError):
			register_to_event(
				self.event_free_cancellable.name,
				{
					"email": None,
					"first_name": None,
					"last_name": 12.34,
					"user": "Administrator",
				},
			)

	@with_user("Guest")
	def test_api_guest_registration_adversarial_2(self):
		with self.assertRaises(frappe.exceptions.InvalidEmailAddressError):
			register_to_event(
				self.event_free_cancellable.name,
				{
					"email": "X",
					"first_name": "Lorem",
					"last_name": "EventRegistration",
					"user": "Administrator",
				},
			)

	@with_user("Guest")
	def test_api_guest_registration_adversarial_3(self):
		register_to_event(
			self.event_free_cancellable.name,
			{
				"email": random_email(),
				"first_name": "Lorem",
				"last_name": "EventRegistration",
				"user": "Administrator",
			},
		)

		my_registrations = self.get_my_registrations()
		self.assertEqual(len(my_registrations), 1)
		self.assertEventRegistration(my_registrations[0].name, self.event_free_cancellable.name, {})
		self.cleanRegistrations(my_registrations)

	@with_user("test@example.com")
	def test_api_registration(self):
		data = {
			"email": random_email(),
			"first_name": "Lorem",
			"last_name": "EventRegistration",
		}
		register_to_event(self.event_free_cancellable.name, data)

		my_registrations = self.get_my_registrations()
		self.assertEqual(len(my_registrations), 1)
		self.assertEventRegistration(my_registrations[0].name, self.event_free_cancellable.name, data)
		self.cleanRegistrations(my_registrations)

	@with_user("test@example.com")
	def test_api_registration_adversarial_1(self):
		with self.assertRaises(frappe.MandatoryError):
			register_to_event(
				self.event_free_cancellable.name,
				{
					"email": None,
					"first_name": None,
					"last_name": 12.34,
					"user": "Administrator",
				},
			)

	@with_user("test@example.com")
	def test_api_registration_adversarial_2(self):
		with self.assertRaises(frappe.exceptions.InvalidEmailAddressError):
			register_to_event(
				self.event_free_cancellable.name,
				{
					"email": "X",
					"first_name": "Lorem",
					"last_name": "EventRegistration",
					"user": "Administrator",
				},
			)

	@with_user("test@example.com")
	def test_api_registration_adversarial_3(self):
		register_to_event(
			self.event_free_cancellable.name,
			{
				"email": random_email(),
				"first_name": "Lorem",
				"last_name": "EventRegistration",
				"user": "Administrator",
			},
		)

		my_registrations = self.get_my_registrations()
		self.assertEqual(len(my_registrations), 1)
		self.assertEventRegistration(my_registrations[0].name, self.event_free_cancellable.name, {})
		self.cleanRegistrations(my_registrations)

	def test_api_cancel_someone_elses_registration_1(self):
		# Create a registration with user test@example.com
		with with_user("test@example.com"):
			reg = register_to_event(
				self.event_free_cancellable.name,
				{
					"email": random_email(),
					"first_name": "Lorem",
					"last_name": "EventRegistration",
				},
			)
			self.addCleanup(self.cleanRegistrations, [reg])

		# Cancel the registration with user Guest
		with with_user("Guest"):
			with self.assertRaises(frappe.PermissionError):
				cancel_registration_by_name(reg.name)

	def test_api_cancel_someone_elses_registration_2(self):
		# Create a registration with user test@example.com
		with with_user("test@example.com"):
			reg = register_to_event(
				self.event_free_cancellable.name,
				{
					"email": random_email(),
					"first_name": "Lorem",
					"last_name": "EventRegistration",
				},
			)
			self.addCleanup(self.cleanRegistrations, [reg])

		# Cancel the registration with user Test 1
		with with_user("test1@example.com"):
			with self.assertRaises(frappe.PermissionError):
				cancel_registration_by_name(reg.name)

	@with_user("Guest")
	def test_api_guest_register_twice_with_different_email(self):
		reg1 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": random_email(),
				"first_name": "Alice",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg1])

		reg2 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": random_email(),
				"first_name": "Bob",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg2])

	@with_user("test@example.com")
	def test_api_register_twice_with_different_email(self):
		reg1 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": random_email(),
				"first_name": "Alice",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg1])

		with self.assertRaises(DuplicateRegistration):
			reg2 = register_to_event(
				self.event_free_cancellable.name,
				{
					"email": random_email(),
					"first_name": "Bob",
					"last_name": "Testuser",
				},
			)
			self.addCleanup(self.cleanRegistrations, [reg2])

	@with_user("Guest")
	def test_api_guest_register_twice_with_same_email(self):
		email = random_email()
		reg1 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": email,
				"first_name": "Alice",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg1])

		with self.assertRaises(DuplicateRegistrationEmail):
			reg2 = register_to_event(
				self.event_free_cancellable.name,
				{
					"email": email,
					"first_name": "Bob",
					"last_name": "Testuser",
				},
			)
			self.addCleanup(self.cleanRegistrations, [reg2])

	@with_user("test@example.com")
	def test_api_register_twice_with_same_email(self):
		email = random_email()
		reg1 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": email,
				"first_name": "Alice",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg1])

		with self.assertRaises(DuplicateRegistration):
			reg2 = register_to_event(
				self.event_free_cancellable.name,
				{
					"email": email,
					"first_name": "Bob",
					"last_name": "Testuser",
				},
			)
			self.addCleanup(self.cleanRegistrations, [reg2])

	@with_user("Guest")
	def test_api_guest_register_twice_with_same_email_if_allowed(self):
		self.event_free_cancellable.db_set("allow_multiple_registrations", 1)

		email = random_email()
		reg1 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": email,
				"first_name": "Alice",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg1])

		reg2 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": email,
				"first_name": "Bob",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg2])

		self.event_free_cancellable.db_set("allow_multiple_registrations", 0)

	@with_user("test@example.com")
	def test_api_register_twice_with_same_email_if_allowed(self):
		self.event_free_cancellable.db_set("allow_multiple_registrations", 1)

		email = random_email()
		reg1 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": email,
				"first_name": "Alice",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg1])

		reg2 = register_to_event(
			self.event_free_cancellable.name,
			{
				"email": email,
				"first_name": "Bob",
				"last_name": "Testuser",
			},
		)
		self.addCleanup(self.cleanRegistrations, [reg2])

		self.event_free_cancellable.db_set("allow_multiple_registrations", 0)
