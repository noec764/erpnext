# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, format_datetime, get_datetime


class EventSlot(Document):
	def validate(self):
		self.validate_dates()
		self.update_dates_in_bookings()

	def validate_dates(self):
		if get_datetime(self.starts_on) > get_datetime(self.ends_on):
			frappe.throw(_("The end time must be greater than the start time"))

	@frappe.whitelist()
	def is_slot_outside_event(self):
		if not self.event:
			return ""

		start, end = frappe.db.get_value("Event", self.event, ["starts_on", "ends_on"])
		is_slot_in_event = get_datetime(self.starts_on) >= get_datetime(start) and get_datetime(
			self.ends_on
		) <= get_datetime(end)
		if not is_slot_in_event:
			return "This slot is outside the event's hours ({0} - {1})".format(
				format_datetime(start), format_datetime(end)
			)
		return ""

	def update_dates_in_bookings(self):
		doc_before_save = self.get_doc_before_save()
		for field in ("starts_on", "ends_on"):
			if not doc_before_save or (
				doc_before_save and getattr(doc_before_save, field, None) != getattr(self, field, None)
			):
				for d in frappe.get_all("Event Slot Booking", filters={"event_slot": self.name}):
					frappe.db.set_value("Event Slot Booking", d.name, field, getattr(self, field, None))


def _get_slots(start, end):
	EventSlot = frappe.qb.DocType("Event Slot")
	query = (
		frappe.qb.from_(EventSlot)
		.select(
			"name",
			"slot_title",
			"starts_on",
			"ends_on",
			"available_bookings",
			"description",
		)
		.where(((EventSlot.starts_on < end) & (EventSlot.ends_on > start)))
	)
	return query.run(as_dict=True)


@frappe.whitelist()
def get_available_slots(start, end):
	slots = _get_slots(start, end)
	slots_names = [x.get("name") for x in slots]

	booked_slots = frappe.get_all(
		"Event Slot Booking", filters={"event_slot": ("in", slots_names)}, fields=["event_slot", "user"]
	)
	booking_count = Counter([x.event_slot for x in booked_slots])

	return [
		dict(
			start=x.starts_on,
			end=x.ends_on,
			id=x.name,
			title=x.slot_title,
			description=get_formatted_description(x, booked_slots, cint(booking_count.get(x.name))),
			content=x.description,
			available_slots=cint(x.available_bookings),
			booked_slots=cint(booking_count.get(x.name)),
			booked_by_user=is_booked_by_user(x, booked_slots),
			textColor="#fff",
			backgroundColor=get_color(x, booked_slots, booking_count),
		)
		for x in slots
	]


def get_formatted_description(slot, booked_slots, booked_number):
	remaining_slots = max(0, cint(slot.available_bookings) - booked_number)
	booked_by_user = is_booked_by_user(slot, booked_slots)
	html = f"""
		<p class="card-text">{remaining_slots} {_("slot available") if remaining_slots in (0, 1) else _("slots available")}</p>
	"""

	if booked_by_user:
		html += f"""
			<p>{_("You are registered")}</p>
		"""

	return f"""
		<div>
			<h6 class="card-title" style="color:inherit;">{slot.slot_title}</h6>
			{html}
		</div>
	"""


def get_color(slot, booked_slots, booking_count):
	booked_by_user = is_booked_by_user(slot, booked_slots)
	if booked_by_user:
		return "#3788d8"
	elif cint(slot.available_bookings) <= cint(booking_count.get(slot.name)):
		return "gray"
	else:
		return "green"


def is_booked_by_user(slot, booked_slots):
	return any(x.user == frappe.session.user for x in booked_slots if x.event_slot == slot.name)
