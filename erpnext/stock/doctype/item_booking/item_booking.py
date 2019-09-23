# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_time, now_datetime, cint, get_datetime, format_datetime
import datetime
from datetime import timedelta, date
import calendar
import json
from erpnext.shopping_cart.cart import update_cart, _get_cart_quotation

class ItemBooking(Document):
	pass

@frappe.whitelist(allow_guest=True)
def get_item_uoms(item_code):
	return {
		"uoms": frappe.get_all('UOM Conversion Detail',\
		filters={'parent': item_code}, fields=["distinct uom"], as_list=1),
		"sales_uom": frappe.db.get_value("Item", item_code, "sales_uom")
	}

@frappe.whitelist()
def book_new_slot(**kwargs):
	quotation = kwargs.get("quotation")
	uom = kwargs.get("uom") or frappe.db.get_value("Item", kwargs.get("item"), "sales_uom")
	if not frappe.session.user == "Guest":
		if not quotation:
			quotation = _get_cart_quotation().get("name")

		if not quotation or not frappe.db.exists("Quotation", quotation):
			quotation = update_cart(item_code=kwargs.get("item"), qty=1, uom=uom).get("name")

	try:
		doc = frappe.get_doc({
			"doctype": "Item Booking",
			"item": kwargs.get("item"),
			"starts_on": kwargs.get("start"),
			"ends_on": kwargs.get("end"),
			"billing_qty": 1,
			"sales_uom": uom,
			"reference_doctype": "Quotation",
			"reference_name": quotation,
			"party": frappe.db.get_value("Quotation", quotation, "party_name"),
			"user": frappe.session.user
		}).insert(ignore_permissions=True)

		return doc
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("New item booking error"))

@frappe.whitelist()
def remove_booked_slot(name):
	try:
		return frappe.delete_doc("Item Booking", name, ignore_permissions=True, force=True)
	except frappe.TimestampMismatchError:
		frappe.get_doc("Item Booking", name).reload()
		remove_booked_slot(name)

@frappe.whitelist()
def get_booked_slots(quotation=None, uom=None):
	if not quotation and not frappe.session.user == "Guest":
		quotation = _get_cart_quotation().get("name")

	if not quotation:
		return []

	filters = dict(reference_doctype="Quotation", reference_name=quotation, docstatus=0)
	if uom:
		filters["sales_uom"] = uom

	return frappe.get_all("Item Booking", filters=filters)

@frappe.whitelist()
def reset_all_booked_slots():
	slots = get_booked_slots()
	for slot in slots:
		remove_booked_slot(slot.get("name"))

	return slots

@frappe.whitelist()
def get_locale():
	return frappe.local.lang

@frappe.whitelist(allow_guest=True)
def get_availabilities(item, start, end, uom=None, quotation=None):
	item_doc = frappe.get_doc("Item", item)
	if not item_doc.enable_item_booking:
		return []

	duration = get_uom_in_minutes(item_doc, uom)
	if not duration:
		return

	init = datetime.datetime.strptime(start, '%Y-%m-%d')
	finish = datetime.datetime.strptime(end, '%Y-%m-%d')

	output = []
	for dt in daterange(init, finish):
		calendar_availability = _check_availability(item_doc, dt, duration, quotation)
		if calendar_availability:
			output.extend(calendar_availability)

	return output

def _check_availability(item, date, duration, quotation=None):
	date = getdate(date)
	day = calendar.day_name[date.weekday()]

	schedule = get_item_calendar(item)

	availability = []
	schedules = []
	if schedule:
		schedule_for_the_day = filter(lambda x: x.day == day, schedule)

		for line in schedule_for_the_day:
			start = now_datetime()
			if datetime.datetime.combine(date, get_time(line.end_time)) > start:
				if datetime.datetime.combine(date, get_time(line.start_time)) > start:
					start = datetime.datetime.combine(date, get_time(line.start_time))

				schedules.append({
					"start": start,
					"end": datetime.datetime.combine(date, get_time(line.end_time)),
					"duration": datetime.timedelta(minutes=cint(duration))
				})

		if schedules:
			availability.extend(_get_availability_from_schedule(item, schedules, date, quotation))

	return availability

def _get_availability_from_schedule(item, schedules, date, quotation=None):
	available_slots = []
	for line in schedules:
		duration = line.get("duration")

		booked_items = _get_events("Item Booking", line.get("start"), line.get("end"), item)

		scheduled_items = []
		for event in booked_items:
			if (get_datetime(event.starts_on) >= line.get("start")\
				and get_datetime(event.starts_on) <= line.get("end")) \
				or get_datetime(event.ends_on) >= line.get("start"):
				scheduled_items.append(event)

		available_slots.extend(_find_available_slot(date, duration, line, scheduled_items, quotation))

	return available_slots

def _get_events(doctype, start, end, item):
	fields = ["starts_on", "ends_on", "item_name", "name",\
		"docstatus", "reference_doctype", "reference_name"]
	filters = [["Item Booking", "item", "=", item.name]]

	start_date = "ifnull(starts_on, '0001-01-01 00:00:00')"
	end_date = "ifnull(ends_on, '2199-12-31 00:00:00')"

	filters.extend([
		[doctype, start_date, '<=', end],
		[doctype, end_date, '>=', start],
	])

	return frappe.get_list(doctype, fields=fields, filters=filters)

def _find_available_slot(date, duration, line, scheduled_items, quotation=None):
	current_schedule = []
	slots = []
	output = []
	output.extend(_get_selected_slots(scheduled_items, quotation))
	for scheduled_item in scheduled_items:
		try:
			if get_datetime(scheduled_item.get("starts_on")) < line.get("start"):
				current_schedule.append((get_datetime(line.get("start")), get_datetime(scheduled_item.ends_on)))
			elif get_datetime(scheduled_item.get("starts_on")) < line.get("end"):
				current_schedule.append((get_datetime(scheduled_item.get("starts_on")),\
					get_datetime(scheduled_item.get("ends_on"))))
		except Exception:
			frappe.log_error(frappe.get_traceback(), _("Slot availability error"))

	sorted_schedule = list(reduced(sorted(current_schedule, key=lambda x: x[0])))

	slots.extend(_get_all_slots(line.get("start"), line.get("end"), line.get("duration"),\
		sorted_schedule))

	if not slots and not scheduled_items:
		slots.extend(_get_all_slots(line.get("start"), line.get("end"), line.get("duration")))

	for slot in slots:
		output.append(get_available_dict(slot[0], slot[1]))

	return output

def _get_selected_slots(events, quotation=None):
	linked_items = [x for x in events if x.docstatus == 0]
	if not linked_items:
		return []

	if not quotation or quotation == "null":
		quotation = _get_cart_quotation().get("name")

	if quotation:
		linked_items = [x for x in linked_items\
			if x.reference_doctype == "Quotation" and x.reference_name == quotation]

	result = []
	for item in linked_items:
		result.append(get_unavailable_dict(item))

	return result

def _get_all_slots(day_start, day_end, duration, scheduled_items=None):
	interval = int(duration.total_seconds() / 60)

	if scheduled_items:
		slots = sorted([(day_start, day_start)] + scheduled_items + [(day_end, day_end)])
	else:
		slots = sorted([(day_start, day_start)] + [(day_end, day_end)])

	free_slots = []
	for start, end in ((slots[i][1], slots[i + 1][0]) for i in range(len(slots) - 1)):
		while start + timedelta(minutes=interval) <= end:
			free_slots.append([start, start + timedelta(minutes=interval)])
			start += timedelta(minutes=interval)

	return free_slots

def get_available_dict(start, end):
	return {
		"start": start.isoformat(),
		"end": end.isoformat(),
		"id": frappe.generate_hash(length=8),
		"classNames": "available",
		"title": _("Available")
	}

def get_unavailable_dict(event):
	return {
		"start": event.starts_on.isoformat(),
		"end": event.ends_on.isoformat(),
		"id": event.name,
		"backgroundColor": "#69eb94",
		"classNames": "unavailable",
		"title": _("Already booked")
	}

def get_item_calendar(item):
	if not item.item_booking_calendar:
		return frappe.get_doc("Stock Settings", None).default_calendar
	else:
		return item.item_booking_calendar

def get_uom_in_minutes(item, uom=None):
	minute_uom = frappe.db.get_value("Stock Settings", None, "minute_uom")
	if uom == minute_uom:
		return 1

	return frappe.db.get_value("UOM Conversion Factor",\
		dict(from_uom=uom if uom else item.sales_uom, to_uom=minute_uom), "value") or 0

def daterange(start_date, end_date):
	if start_date < now_datetime():
		start_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
	for n in range(int((end_date - start_date).days)):
		yield start_date + timedelta(n)

def reduced(timeseries):
	prev = datetime.datetime.min
	for start, end in timeseries:
		if end > prev:
			prev = end
			yield start, end

def delete_linked_item_bookings(doc, method):
	bookings = get_linked_docs_list(doc)
	for booking in bookings:
		frappe.delete_doc("Item Booking", booking.name, ignore_permissions=True, force=True)

def submit_linked_item_bookings(doc, method):
	bookings = get_linked_docs_list(doc)
	for booking in bookings:
		slot = frappe.get_doc("Item Booking", booking.name)
		slot.flags.ignore_permissions = True
		slot.submit()

def get_linked_docs_list(doc):
	return frappe.get_list("Item Booking", filters={"reference_doctype": doc.doctype, "reference_name": doc.name})

def clear_draft_bookings():
	drafts = frappe.get_all("Item Booking", filters={"docstatus": 0}, fields=["name", "modified"])

	for draft in drafts:
		if draft.get("modified") > now_datetime() + datetime.timedelta(minutes=15):
			remove_booked_slot(draft.get("name"))
