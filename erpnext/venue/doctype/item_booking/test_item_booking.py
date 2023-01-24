# Copyright (c) 2023, Dokos SAS and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase, change_settings

from frappe.utils import add_to_date, getdate

from erpnext import get_default_company
from erpnext.venue.doctype.item_booking.item_booking import get_availabilities

from datetime import datetime, date

TEST_CUSTOMER = "_Test Customer 1"
ALL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

MAX_SIMULTANEOUS_BOOKINGS_1 = 2

class BaseTestWithBookableItem(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()

		cls._old_curr_date = frappe.flags.current_date
		frappe.flags.current_date = None

		cls.ITEM_BOOKABLE_1 = frappe.get_doc({
			"doctype": "Item",
			"item_code": "Coworking space - _Test Item for Item Booking with Subscription",
			"item_group": frappe.get_value("Item Group", [("parent_item_group", "=", "")]),
			"sales_uom": "Hour",
			"is_stock_item": 0,
			"enable_item_booking": 1,
			"simultaneous_bookings_allowed": MAX_SIMULTANEOUS_BOOKINGS_1,
		})
		cls.ITEM_BOOKABLE_1.insert()

		cls.ITEM_SUB_1 = frappe.get_doc({
			"doctype": "Item",
			"item_code": "Monthly subscription coworking - _Test Item for Item Booking with Subscription",
			"item_group": frappe.get_value("Item Group", [("parent_item_group", "=", "")]),
			"sales_uom": "Unit",
		})
		cls.ITEM_SUB_1.insert()

		# cls.ITEM_TICKET_1 = frappe.get_doc({
		# 	"doctype": "Item",
		# 	"item_code": "Coworking ticket - _Test Item for Item Booking with Subscription",
		# 	"item_group": frappe.get_value("Item Group", [("parent_item_group", "=", "")]),
		# 	"sales_uom": "Unit",
		# })
		# cls.ITEM_TICKET_1.insert()

		cls.CALENDAR_1 = frappe.get_doc({
			# This is the actual time slots available for your test item
			"doctype": "Item Booking Calendar",
			"calendar_title": "_Test Booking Calendar for Item Booking with Subscription",
			"uom": None,
			"item": cls.ITEM_BOOKABLE_1.name,
			"calendar_type": "Daily",
			"booking_calendar": [
				{ "day": d, "start_time": "08:00:00", "end_time": "18:00:00" }
				for d in ALL_DAYS
			],
		})
		cls.CALENDAR_1.insert()

	@classmethod
	def tearDownClass(cls) -> None:
		frappe.flags.current_date = cls._old_curr_date
		return super().tearDownClass()

	def makeBookingWithAutocleanup(self, *args, **kwargs):
		booking = self.makeBooking(*args, **kwargs)
		self.addCleanup(booking.delete)
		return booking

	def makeBooking(self, booked_item: str, start: datetime, end: datetime, user: str = None, all_day = False, uom = "Hour"):
		booking = frappe.get_doc({
			"doctype": "Item Booking",
			"item": booked_item,
			"starts_on": start,
			"ends_on": end,
			"user": user,
			"status": "Confirmed",
			"all_day": all_day,
			"uom": uom,
			"sync_with_google_calendar": False,
		})
		booking.insert()
		return booking


class BaseTestWithSubscriptionForBookableItem(BaseTestWithBookableItem):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()

		cls.SUBSCRIPTION_TEMPLATE_1 = cls.createSubscriptionTemplateForItem(
			"_Test Subscription Template for Item Booking with Subscription",
			item_name=cls.ITEM_SUB_1.name, qty=1,  # You buy 1 monthly subscription.
			booked_item=cls.ITEM_BOOKABLE_1.name,  # And it subtracts 1 available slot for every period (hour) for the booked_item.
		)

	@classmethod
	def createSubscriptionTemplateForItem(cls, template_name: str, item_name: str, qty: int, booked_item: str):
		plan = frappe.get_doc({
			"doctype": "Subscription Plan",
			"plan_name": template_name + "_PLAN",
			"subscription_plans_template": [{
				"item": item_name,
				"qty": qty,
				"booked_item": booked_item,
				# TODO: Add checkbox for autoreserve
			}]
		})
		plan.insert()

		template = frappe.get_doc({
			"doctype": "Subscription Template",
			"template_name": template_name,
			"subscription_plan": plan.name,
		})
		template.insert()

		return template

	@classmethod
	def makeSubscription(self, start_date, *, customer: str = TEST_CUSTOMER, template: dict = None, company: str = get_default_company()):
		if isinstance(start_date, date):
			pass  # ok
		elif isinstance(start_date, datetime):
			start_date = start_date.date()  # convert for convenience
		elif len(str(start_date)) != 10:
			raise ValueError("testing: makeSubscription(...) start_date parameter must be a `date` object, got a " + repr(type(start_date)))

		template = template or self.SUBSCRIPTION_TEMPLATE_1
		return template.make_subscription(customer=customer, company=company, start_date=start_date)


class TestItemBooking(BaseTestWithBookableItem):
	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 1, "no_overlap_per_item": 1 })
	def test_booking1(self):
		dt_start = add_to_date(getdate(), days=1, hours=8, minutes=0)  # 8:00
		dt_end = add_to_date(dt_start, hours=1)  # 9:00
		self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start, dt_end)  # Create a booking

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 0, "no_overlap_per_item": 1 })
	def test_booking2(self):  # identical, but without simultaneous bookings
		dt_start = add_to_date(getdate(), days=1, hours=8, minutes=0)  # 8:00
		dt_end = add_to_date(dt_start, hours=1)  # 9:00
		self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start, dt_end)

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 0, "no_overlap_per_item": 1 })
	def test_booking_overlap_exact_same_dt(self):
		dt_start = add_to_date(getdate(), days=1, hours=8, minutes=0)  # 8:00
		dt_end = add_to_date(dt_start, hours=1)  # 9:00
		self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start, dt_end)

		with self.assertRaises(frappe.ValidationError):
			# Here we try to book on the exact same slot: this should raise an exception.
			self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start, dt_end)

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 0, "no_overlap_per_item": 1 })
	def test_booking_overlap_when_bigger(self):
		dt_start2 = add_to_date(getdate(), days=1, hours=8, minutes=0)  # 8:00
		dt_start1 = add_to_date(dt_start2, hours=1)  # 9:00
		dt_end1 = add_to_date(dt_start1, hours=1)  # 10:00
		dt_end2 = add_to_date(dt_end1, hours=1)  # 11:00
		booking_1 = self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start1, dt_end1)

		with self.assertRaises(frappe.ValidationError):
			# Here we try to book "around" the existing booking.
			booking_2 = self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start2, dt_end2)

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 0, "no_overlap_per_item": 1 })
	def test_booking_no_overlap_with_start_equals_end(self):
		dt_start1 = add_to_date(getdate(), days=1, hours=8, minutes=0)  # 8:00
		dt_end1 = add_to_date(dt_start1, hours=1)  # 9:00
		dt_start2 = dt_end1  # 9:00
		dt_end2 = add_to_date(dt_start2, hours=1)  # 10:00
		booking_1 = self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start1, dt_end1)
		booking_2 = self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start2, dt_end2)

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 0, "no_overlap_per_item": 1 })
	def test_booking_no_overlap_with_start_equals_end_reversed(self):
		dt_start1 = add_to_date(getdate(), days=1, hours=8, minutes=0)  # 8:00
		dt_end1 = add_to_date(dt_start1, hours=1)  # 9:00
		dt_start2 = dt_end1  # 9:00
		dt_end2 = add_to_date(dt_start2, hours=1)  # 10:00
		booking_2 = self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start2, dt_end2)  # order is reversed
		booking_1 = self.makeBookingWithAutocleanup(self.ITEM_BOOKABLE_1.name, dt_start1, dt_end1)

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 0, "no_overlap_per_item": 0 })
	def test_all_kinds_of_bookings(self):
		from contextlib import contextmanager
		@contextmanager
		def make(dt_start, dt_end):
			booking = self.makeBooking(self.ITEM_BOOKABLE_1.name, dt_start, dt_end)  # Create a booking
			yield booking
			booking.delete()

		"""
			6  7  8  9 10~16 17 18 19 20 Timeline
			......|______________|...... Overlap?
			...AAAAAAA..BBBB..CCCCCCC... yes
			......DDDD........EEEE...... yes
			......FFFFFFFFFFFFFFFF...... yes
			...GGGGGGGGGGGGGGGGGGGGGG... yes
			...XXXX..............WWWW... NO
			......U..............V...... NO
			ZZZZ....................YYYY NO
		"""

		cases = [
			# hour start, hour end, expected number of availabilities (10)
			(7, 9, "=", 9),
			(10, 16, "=", 4),
			(17, 19, "=", 9),
			(8, 9, "=", 9),
			(17, 18, "=", 9),
			(8, 18, "=", 0),
			(7, 19, "=", 0),
			(7, 8, "=", 10),
			(18, 19, "=", 10),
			(8, 8, "=", 10),
			(18, 18, "=", 10),
			(6, 7, "=", 10),
			(19, 20, "=", 10),
		]

		dt_now = add_to_date(getdate(), days=2, hours=0, minutes=0, seconds=0)

		def t(hour):
			return add_to_date(dt_now, hours=hour)

		for start, end, _, expected in cases:
			try:
				with make(t(start), t(end)) as b:
					availabilities = get_availabilities(
						self.ITEM_BOOKABLE_1.name,
						start=dt_now,
						end=add_to_date(dt_now, days=1),
						uom="Hour")
					self.assertEqual(len(availabilities), expected)  # 10 hours between 8:00-18:00
					break
			except:
				print("Case:", start, end, _, expected)
				raise

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 1 })
	def test_availability_on_customer_interface(self):
		dt_start = add_to_date(getdate(), days=4, hours=7)
		dt_end = add_to_date(dt_start, days=1)

		availabilities = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,  # NOTE: Only the date is taken into account
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities), 10)  # 10 hours between 8:00-18:00

		for i, a in enumerate(availabilities):
			start: str = a["start"]
			end: str = a["end"]
			taken: int = a["number"]
			avail: int = a["total_available"]
			self.assertTrue(start.endswith(str(i + 8).rjust(2, "0") + ":00:00"))
			self.assertTrue(end.endswith(str(i + 8 + 1).rjust(2, "0") + ":00:00"))
			self.assertEqual(taken, 0)
			self.assertEqual(avail, MAX_SIMULTANEOUS_BOOKINGS_1)

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 1 })
	def test_availability_in_the_future(self):
		dt_start = add_to_date(getdate(), days=4, hours=7)
		dt_end = add_to_date(dt_start, days=1)

		availabilities = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities), 10)  # 10 hours between 8:00-18:00


class TestItemBookingWithSubscription(BaseTestWithSubscriptionForBookableItem):
	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 1 })
	def test_subscription_decreases_availability1(self):
		dt_sub_start = add_to_date(getdate(), days=2)
		subscription = self.makeSubscription(start_date=dt_sub_start)
		self.addCleanup(subscription.delete)

		dt_start = add_to_date(getdate(), days=4, hours=7)
		dt_end = add_to_date(dt_start, days=1)

		availabilities = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities), 10)  # 10 hours between 8:00-18:00

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 1 })
	def test_subscription_decreases_availability2(self):
		dt_sub_start = add_to_date(getdate(), days=2)
		subscription1 = self.makeSubscription(start_date=dt_sub_start)
		subscription2 = self.makeSubscription(start_date=dt_sub_start)
		self.addCleanup(subscription1.delete)
		self.addCleanup(subscription2.delete)

		dt_start = add_to_date(getdate(), days=4, hours=7)
		dt_end = add_to_date(dt_start, days=1)

		availabilities = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities), 0)

	@change_settings("Venue Settings", {
		"minute_uom": "Minute",
		# NOTE: Disable simultaneous booking (so that only 1 subscription is needed to take all the booking slots)
		"enable_simultaneous_booking": 0,
	})
	def test_successive_subscription_decreases_availability(self):
		dt_start = add_to_date(getdate(), days=4, hours=7)
		dt_mid = add_to_date(dt_start, days=1)
		dt_end = add_to_date(dt_start, days=2)

		subscription = self.makeSubscription(start_date=dt_mid)
		self.addCleanup(subscription.delete)

		availabilities1 = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_mid,
			uom="Hour")
		self.assertEqual(len(availabilities1), 10)  # 10 hours between 8:00-18:00

		availabilities2 = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_mid,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities2), 0)  # subscription started

		availabilities_full = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities_full), 10)  # 10 hours of the first period

	@change_settings("Venue Settings", {
		"minute_uom": "Minute",
		"enable_simultaneous_booking": 0,
	})
	def test_cancelled_subscription(self):
		dt_start = add_to_date(getdate(), days=4, hours=7)
		dt_end = add_to_date(dt_start, days=1)

		subscription = self.makeSubscription(start_date=dt_start)
		self.addCleanup(subscription.delete)

		availabilities1 = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities1), 0)  # The subscription is active

		subscription.cancel_subscription(cancellation_date=dt_start.date())

		availabilities2 = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities2), 10)  # The subscription was cancelled

	@change_settings("Venue Settings", {
		"minute_uom": "Minute",
		"enable_simultaneous_booking": 0,
	})
	def test_subscription_just_started_and_just_ended(self):
		dt_base = add_to_date(getdate(), days=4, hours=7)  # Reference
		dt_sub_start = add_to_date(dt_base, days=1)
		dt_sub_end = add_to_date(dt_base, days=2)
		dt_end = add_to_date(dt_base, days=3)

		def count_slots(start, end):
			return (end - start).days * 10  # 10 slots per day
		assert count_slots(dt_base, dt_end) == 30, "invariant failed: date difference is not correct"
		assert count_slots(dt_base, dt_sub_start) == 10, "invariant failed: date difference is not correct"
		assert count_slots(dt_sub_start, dt_sub_end) == 10, "invariant failed: date difference is not correct"
		assert count_slots(dt_sub_end, dt_end) == 10, "invariant failed: date difference is not correct"

		n_slots1 = count_slots(dt_base, dt_sub_start)
		availabilities1 = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_base,
			end=dt_sub_start,
			uom="Hour")
		self.assertEqual(len(availabilities1), n_slots1)  # subscription does not even exist

		subscription = self.makeSubscription(start_date=dt_sub_start)
		self.addCleanup(subscription.delete)
		subscription.cancel_subscription(cancellation_date=dt_sub_end.date())

		self.assertEqual(len(get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_base,
			end=dt_sub_start,
			uom="Hour")
		), count_slots(dt_base, dt_sub_start))  # subscription not started yet

		self.assertEqual(len(get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_sub_start,
			end=dt_sub_end,
			uom="Hour")
		), 0)  # subscription just started and ended

		self.assertEqual(len(get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_sub_end,
			end=dt_end,
			uom="Hour")
		), count_slots(dt_sub_end, dt_end))  # subscription already ended

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 0 })
	def test_availability_with_non_booking_subscription(self):
		dt_sub_start = getdate()
		dt_start = add_to_date(dt_sub_start, days=4, hours=7)
		dt_end = add_to_date(dt_start, days=1)

		availabilities = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities), 10)  # 10 hours between 8:00-18:00

		sub_template = self.createSubscriptionTemplateForItem(
			"_Test Subscription Template 2 for Not Bookable",
			item_name=self.ITEM_SUB_1.name, qty=1,
			booked_item=None,  # This subscription should not have an impact on bookings
		)
		self.addCleanup(sub_template.delete)
		subscription = self.makeSubscription(start_date=dt_sub_start, template=sub_template)
		self.addCleanup(subscription.delete)

		availabilities = get_availabilities(
			self.ITEM_BOOKABLE_1.name,
			start=dt_start,
			end=dt_end,
			uom="Hour")
		self.assertEqual(len(availabilities), 10)  # 10 hours between 8:00-18:00

	@change_settings("Venue Settings", { "minute_uom": "Minute", "enable_simultaneous_booking": 0 })
	def TODO__test_availability_for_specific_user(self):
		...
