# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from collections import Counter 

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, global_date_format, format_time, cint

class EventSlot(Document):
	def validate(self):
		self.validate_dates()
		self.update_dates_in_bookings()

	def validate_dates(self):
		start, end = frappe.db.get_value("Event", self.event, ["starts_on", "ends_on"])
		if get_datetime(self.starts_on) < get_datetime(start):
			frappe.throw(_("The start time cannot be before {0}").format(global_date_format(get_datetime(start)) + ' ' + format_time(get_datetime(start))))

		if get_datetime(self.ends_on) > get_datetime(end):
			frappe.throw(_("The end time cannot be after {0}").format(global_date_format(get_datetime(end)) + ' ' + format_time(get_datetime(end))))

	def update_dates_in_bookings(self):
		doc_before_save = self.get_doc_before_save()
		for field in ("starts_on", "ends_on"):
			if not doc_before_save or (doc_before_save and getattr(doc_before_save, field, None) != getattr(self, field, None)):
				for d in frappe.get_all("Event Slot Booking", filters={"event_slot": self.name}):
					frappe.db.set_value("Event Slot Booking", d.name, field, getattr(self, field, None))

@frappe.whitelist()
def get_events(start, end, filters):
	from frappe.desk.calendar import get_event_conditions
	conditions = get_event_conditions("Event Slot Booking", filters)

	slots = _get_slots(start, end, filters, conditions)

	bookings = frappe.db.sql("""
		select
			`tabEvent Slot Booking`.name,
			`tabEvent Slot Booking`.event_slot,
			`tabEvent Slot Booking`.user_name as event_subject,
			`tabEvent Slot Booking`.starts_on,
			`tabEvent Slot Booking`.ends_on

		from
			`tabEvent Slot Booking`
		WHERE (
				(
					(date(`tabEvent Slot Booking`.starts_on) BETWEEN date(%(start)s) AND date(%(end)s))
					OR (date(`tabEvent Slot Booking`.ends_on) BETWEEN date(%(start)s) AND date(%(end)s))
					OR (
						date(`tabEvent Slot Booking`.starts_on) <= date(%(start)s)
						AND date(`tabEvent Slot Booking`.ends_on) >= date(%(end)s)
					)
				)
			)
			{conditions}
		""".format(conditions=conditions), {
			"start": start,
			"end": end
		}, as_dict=True)

	data = [dict({
		"doctype": "Event Slot",
		"redirect_id": x.get("event_slot")
	}, **x) for x in bookings]

	data.extend([dict({
		"display": "background"
	}, **x) for x in slots])

	return data

def _get_slots(start, end, filters=None, conditions=None):
	return frappe.db.sql("""
		select
			`tabEvent Slot`.name,
			`tabEvent Slot`.event_subject,
			`tabEvent Slot`.starts_on,
			`tabEvent Slot`.ends_on,
			`tabEvent Slot`.available_bookings,
			`tabEvent Slot`.description
		from
			`tabEvent Slot`
		WHERE (
				(
					(date(`tabEvent Slot`.starts_on) BETWEEN date(%(start)s) AND date(%(end)s))
					OR (date(`tabEvent Slot`.ends_on) BETWEEN date(%(start)s) AND date(%(end)s))
					OR (
						date(`tabEvent Slot`.starts_on) <= date(%(start)s)
						AND date(`tabEvent Slot`.ends_on) >= date(%(end)s)
					)
				)
			)
			{conditions}
		""".format(conditions=conditions or ""), {
			"start": start,
			"end": end
		}, as_dict=True)

@frappe.whitelist()
def get_available_slots(start, end):
	slots = _get_slots(start, end)
	slots_names = [x.get("name") for x in slots]

	bookings = Counter([x.event_slot for x in frappe.get_all("Event Slot Booking", filters={"event_slot": ("in", slots_names)}, fields=["event_slot"])])

	return [dict(
		start=x.starts_on,
		end=x.ends_on,
		id=x.name,
        title=x.event_subject,
		description=get_formatted_description(x, cint(bookings.get(x.name))),
		content=x.description,
		available_slots=cint(x.available_bookings),
		booked_slots=cint(bookings.get(x.name)),
		textColor='#fff',
		display='background' if cint(bookings.get(x.name)) >= cint(x.available_bookings) else None,
		backgroundColor='#3788d8' if cint(bookings.get(x.name)) >= cint(x.available_bookings) else get_color(cint(x.available_bookings), cint(bookings.get(x.name))),
	) for x in slots]

def get_formatted_description(slot, booked_slots):
	remaining_slots = max(0, cint(slot.available_bookings) - booked_slots)
	return f"""
		<p>🡒 {remaining_slots} {_("slot available") if remaining_slots in (0, 1) else _("slots available")}</p>
	"""

def get_color(available_slots, booked_slots):
	if available_slots > booked_slots:
		return "green"
	else:
		return "gray"