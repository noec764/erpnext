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
from frappe.desk.calendar import get_rrule
from dateutil import parser
from erpnext.shopping_cart.cart import update_cart, _get_cart_quotation
from erpnext.utilities.product import get_price
from erpnext.shopping_cart.product_info import get_product_info_for_website
from erpnext.shopping_cart.doctype.shopping_cart_settings.shopping_cart_settings import get_shopping_cart_settings
from frappe.model.mapper import get_mapped_doc
from erpnext.accounts.party import get_party_account_currency
from frappe.utils.user import is_website_user
from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object, \
	format_date_according_to_google_calendar, get_timezone_naive_datetime
from googleapiclient.errors import HttpError

class ItemBooking(Document):
	def before_save(self):
		if self.user:
			user_name = frappe.db.get_value("User", self.user, "full_name")
			self.title = self.item_name + " - " + user_name or self.user
		else:
			self.title = self.item_name

		if self.sync_with_google_calendar and not self.google_calendar:
			self.google_calendar = frappe.db.get_value("Item", self.item, "google_calendar")

		if self.google_calendar and not self.google_calendar_id:
			self.google_calendar_id = frappe.db.get_value("Google Calendar", self.google_calendar, "google_calendar_id")

		if isinstance(self.rrule, list) and self.rrule > 1:
			self.rrule = self.rrule[0]

def get_list_context(context=None):
	context.update({
		"show_sidebar": True,
		"show_search": True,
		'no_breadcrumbs': True,
		"title": _("Bookings"),
		"get_list": get_bookings_list,
		"row_template": "templates/includes/item_booking_row.html",
		"create_new": "/",
		"can_cancel": frappe.has_permission("Item Booking", "cancel")
	})

def get_bookings_list(doctype, txt, filters, limit_start, limit_page_length = 20, order_by = None):
	from frappe.www.list import get_list
	user = frappe.session.user
	contact = frappe.db.get_value('Contact', {'user': user}, 'name')
	customer = None

	if contact:
		contact_doc = frappe.get_doc('Contact', contact)
		customer = contact_doc.get_link_for('Customer')

	if is_website_user():
		if not filters: filters = []

		or_filters = []
		or_filters.append({"user": user, "party_name": customer})

	return get_list(doctype, txt, filters, limit_start, limit_page_length, ignore_permissions=False, or_filters=or_filters)

@frappe.whitelist()
def cancel_appointments(ids, force=False):
	ids = frappe.parse_json(ids)
	for id in ids:
		cancel_appointment(id, force)

@frappe.whitelist()
def cancel_appointment(id, force=False):
	booking = frappe.get_doc("Item Booking", id)
	if force:
		booking.flags.ignore_links = True
	return booking.cancel()

@frappe.whitelist(allow_guest=True)
def get_item_uoms(item_code):
	return {
		"uoms": frappe.get_all('UOM Conversion Detail',\
		filters={'parent': item_code}, fields=["distinct uom"], order_by='idx desc', as_list=1),
		"sales_uom": frappe.db.get_value("Item", item_code, "sales_uom")
	}

@frappe.whitelist(allow_guest=True)
def get_item_price(item_code, uom):
	cart_settings = get_shopping_cart_settings()

	if not cart_settings.enabled:
		return frappe._dict()

	cart_quotation = _get_cart_quotation()

	price = get_price(
		item_code=item_code,
		price_list=cart_quotation.selling_price_list,
		customer_group=cart_settings.default_customer_group,
		company=cart_settings.company,
		uom=uom
	)

	return {
		"item_name": frappe.db.get_value("Item", item_code, "item_name"),
		"price": price
	}

@frappe.whitelist()
def book_new_slot(**kwargs):
	uom = kwargs.get("uom") or frappe.db.get_value("Item", kwargs.get("item"), "sales_uom")
	try:
		doc = frappe.get_doc({
			"doctype": "Item Booking",
			"item": kwargs.get("item"),
			"starts_on": kwargs.get("start"),
			"ends_on": kwargs.get("end"),
			"billing_qty": 1,
			"sales_uom": uom,
			"user": frappe.session.user
		}).insert(ignore_permissions=True)

		return doc
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("New item booking error"))

@frappe.whitelist()
def remove_booked_slot(name):
	try:
		for dt in ["Quotation Item", "Sales Order Item"]:
			linked_docs = frappe.get_all(dt, filters={"item_booking": name})
			for d in linked_docs:
				frappe.db.set_value(dt, d.get("name"), "item_booking", None)

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

	filters = dict(parenttype="Quotation", parent=quotation)
	if uom:
		filters["uom"] = uom

	return frappe.get_all("Quotation Item", filters=filters, fields=["item_booking as name"])

@frappe.whitelist()
def reset_all_booked_slots():
	slots = get_booked_slots()
	for slot in slots:
		remove_booked_slot(slot.get("name"))

	return slots

@frappe.whitelist(allow_guest=True)
def get_locale():
	return frappe.local.lang

@frappe.whitelist(allow_guest=True)
def get_available_item(item, start, end):
	alternative_items = frappe.get_all("Item", \
		filters={"show_in_website": 1, "enable_item_booking": 1, "item_code": ["!=", item]}, \
		fields=["name", "item_name", "route", "website_image", "image", "description", "website_content"])

	available_items = []
	for alternative_item in alternative_items:
		availabilities = get_availabilities(alternative_item.name, start, end)
		if len(availabilities):
			available_items.append(alternative_item)

	result = []
	for available_item in available_items:
		product_info = get_product_info_for_website(available_item.name)
		if product_info.product_info and product_info.product_info.get("price") \
			and (product_info.cart_settings.get("allow_items_not_in_stock") \
			or product_info.product_info.get("in_stock")):
			result.append(available_item)

	return result

@frappe.whitelist(allow_guest=True)
def get_availabilities(item, start, end, uom=None, quotation=None):
	item_doc = frappe.get_doc("Item", item)
	if not item_doc.enable_item_booking:
		return []

	if not uom:
		uom = item_doc.sales_uom

	duration = get_uom_in_minutes(uom)
	if not duration:
		return

	init = datetime.datetime.strptime(start, '%Y-%m-%d')
	finish = datetime.datetime.strptime(end, '%Y-%m-%d')

	output = []
	for dt in daterange(init, finish):
		calendar_availability = _check_availability(item_doc, dt, duration, quotation, uom)
		if calendar_availability:
			output.extend(calendar_availability)

	return output

def _check_availability(item, date, duration, quotation=None, uom=None):
	date = getdate(date)
	day = calendar.day_name[date.weekday()]


	schedule = get_item_calendar(item.name, uom)

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

		available_slots.extend(_find_available_slot(date, duration, line, scheduled_items, item, quotation))

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

def _find_available_slot(date, duration, line, scheduled_items, item, quotation=None):
	current_schedule = []
	slots = []
	output = []
	output.extend(_get_selected_slots(scheduled_items, quotation))

	simultaneous_booking_allowed = frappe.db.get_value("Stock Settings", None, "enable_simultaneous_booking")
	if simultaneous_booking_allowed:
		scheduled_items = check_simultaneaous_bookings(item, scheduled_items)

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
		simultaneous_booking_allowed, sorted_schedule))

	if not slots and not scheduled_items:
		slots.extend(_get_all_slots(line.get("start"), line.get("end"), line.get("duration"), simultaneous_booking_allowed))

	for slot in slots:
		output.append(get_available_dict(slot[0], slot[1]))

	return output

def check_simultaneaous_bookings(item, scheduled_items):
	import itertools
	from operator import itemgetter

	simultaneous_bookings = item.get("simultaneous_bookings_allowed")
	if simultaneous_bookings > 1:
		sorted_schedule = sorted(scheduled_items, key=itemgetter('starts_on'))
		for key, group in itertools.groupby(sorted_schedule, key=lambda x: x['starts_on']):
			grouped_sch = [x.get("name") for x in list(group)]
			if len(grouped_sch) == simultaneous_bookings:
				scheduled_items = [x for x in scheduled_items if x.get("name") not in grouped_sch[:-1]]
			elif len(grouped_sch) < simultaneous_bookings:
				scheduled_items = [x for x in scheduled_items if x.get("name") not in grouped_sch]

	return scheduled_items

def _get_selected_slots(events, quotation=None):
	linked_items = [x for x in events if x.docstatus == 0]
	if not linked_items:
		return []

	if not quotation or quotation == "null":
		quotation = _get_cart_quotation().get("name")

	if quotation:
		quotation_items = [x["item_booking"] for x in frappe.get_all("Quotation Item", \
			filters={"parenttype": "Quotation", "parent": quotation}, fields=["item_booking"]) if x["item_booking"] is not None]

		linked_items = [x for x in linked_items if x.name in quotation_items]

	result = []
	for item in linked_items:
		result.append(get_unavailable_dict(item))

	return result

def _get_all_slots(day_start, day_end, duration, simultaneous_booking_allowed, scheduled_items=None):
	interval = int(duration.total_seconds() / 60)

	slots = sorted([(day_start, day_start)] + [(day_end, day_end)])

	if simultaneous_booking_allowed:
		vanilla_start_times = []
		for start, end in ((slots[i][0], slots[i + 1][0]) for i in range(len(slots) - 1)):
			while start + timedelta(minutes=interval) <= end:
				vanilla_start_times.append(start)
				start += timedelta(minutes=interval)

	if scheduled_items:
		slots = sorted([(day_start, day_start)] + scheduled_items + [(day_end, day_end)])

	free_slots = []
	for start, end in ((slots[i][1], slots[i + 1][0]) for i in range(len(slots) - 1)):
		while start + timedelta(minutes=interval) <= end:
			if simultaneous_booking_allowed:
				if start not in vanilla_start_times:
					vanilla_start = [x for x in vanilla_start_times if start + timedelta(minutes=interval) <= x]
					if vanilla_start:
						start = vanilla_start[0]
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
		"title": _("In shopping cart")
	}

def get_item_calendar(item, uom):
	calendars = frappe.get_all("Item Booking Calendar", fields=["name", "item", "uom"])
	for filters in [dict(item=item, uom=uom), dict(item=item, uom=None),\
		dict(item=None, uom=uom), dict(item=None, uom=None)]:
		filtered_calendars = [x.get("name") for x in calendars if x.get("item") == filters.get("item") and x.get("uom") == filters.get("uom")]
		if filtered_calendars:
			return frappe.get_doc("Item Booking Calendar", filtered_calendars[0]).booking_calendar
	return []

def get_uom_in_minutes(uom=None):
	minute_uom = frappe.db.get_value("Stock Settings", None, "minute_uom")
	if uom == minute_uom:
		return 1

	return frappe.db.get_value("UOM Conversion Factor",\
		dict(from_uom=uom, to_uom=minute_uom), "value") or 0

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
	for item in doc.items:
		if item.item_booking:
			frappe.delete_doc("Item Booking", item.item_booking, ignore_permissions=True, force=True)

def submit_linked_item_bookings(doc, method):
	for item in doc.items:
		if item.item_booking:
			slot = frappe.get_doc("Item Booking", item.item_booking)
			slot.flags.ignore_permissions = True
			slot.submit()

def clear_draft_bookings():
	drafts = frappe.get_all("Item Booking", filters={"docstatus": 0}, fields=["name", "modified"])
	clearing_duration = frappe.db.get_value("Stock Settings", None, "clear_item_booking_draft_duration")

	if cint(clearing_duration) <= 0:
		return

	for draft in drafts:
		if now_datetime() > draft.get("modified") + datetime.timedelta(minutes=cint(clearing_duration)):
			remove_booked_slot(draft.get("name"))

@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	def set_missing_values(source, target):
		from erpnext.controllers.accounts_controller import get_default_taxes_and_charges
		quotation = frappe.get_doc(target)
		quotation.order_type = "Maintenance"
		company_currency = frappe.get_cached_value('Company',  quotation.company,  "default_currency")

		if quotation.quotation_to == 'Customer' and quotation.party_name:
			party_account_currency = get_party_account_currency("Customer", quotation.party_name, quotation.company)
		else:
			party_account_currency = company_currency

		quotation.currency = party_account_currency or company_currency

		if company_currency == quotation.currency:
			exchange_rate = 1
		else:
			exchange_rate = get_exchange_rate(quotation.currency, company_currency,
				quotation.transaction_date, args="for_selling")

		quotation.conversion_rate = exchange_rate

		# add item
		quotation.append('items', {
			'item_code': source.item,
			'qty': source.billing_qty,
			'uom': source.sales_uom,
			'item_booking': source.name
		})

		# get default taxes
		taxes = get_default_taxes_and_charges("Sales Taxes and Charges Template", company=quotation.company)
		if taxes.get('taxes'):
			quotation.update(taxes)

		quotation.run_method("set_missing_values")
		quotation.run_method("calculate_taxes_and_totals")

	doclist = get_mapped_doc("Item Booking", source_name, {
		"Item Booking": {
			"doctype": "Quotation",
			"field_map": {
				"party_type": "quotation_to"
			}
		}
	}, target_doc, set_missing_values)

	doc = frappe.get_doc(doclist).insert()
	frappe.db.set_value("Item Booking", source_name, "reference_doctype", doc.doctype)
	frappe.db.set_value("Item Booking", source_name, "reference_name", doc.name)

	return doc

def get_calendar_item(account):
	return frappe.db.get_value("Item", dict(google_calendar=account.name), "item_code")

def insert_event_to_calendar(account, event, recurrence=None):
	"""
		Inserts event in Dokos Calendar during Sync
	"""
	start = event.get("start")
	end = event.get("end")

	calendar_event = {
		"doctype": "Item Booking",
		"item": get_calendar_item(account),
		"notes": event.get("description"),
		"sync_with_google_calendar": 1,
		"google_calendar": account.name,
		"google_calendar_id": account.google_calendar_id,
		"google_calendar_event_id": event.get("id"),
		"rrule": recurrence,
		"starts_on": get_datetime(start.get("date")) if start.get("date") else get_timezone_naive_datetime(start),
		"ends_on": get_datetime(end.get("date")) if end.get("date") else get_timezone_naive_datetime(end),
		"all_day": 1 if start.get("date") else 0,
		"repeat_this_event": 1 if recurrence else 0
	}
	doc = frappe.get_doc(calendar_event)
	doc.flags.pulled_from_google_calendar = True
	doc.insert(ignore_permissions=True)
	doc.submit()

def update_event_in_calendar(account, event, recurrence=None):
	"""
		Updates Event in Dokos Calendar if any existing Google Calendar Event is updated
	"""
	start = event.get("start")
	end = event.get("end")

	calendar_event = frappe.get_doc("Item Booking", {"google_calendar_event_id": event.get("id")})

	updated_event = {
		"item": get_calendar_item(account),
		"notes": event.get("description"),
		"rrule": recurrence,
		"starts_on": get_datetime(start.get("date")) if start.get("date") else get_timezone_naive_datetime(start),
		"ends_on": get_datetime(end.get("date")) if end.get("date") else get_timezone_naive_datetime(end),
		"all_day": 1 if start.get("date") else 0,
		"repeat_this_event": 1 if recurrence else 0
	}

	update = False
	for field in updated_event:
		if calendar_event.get(field) != updated_event.get(field):
			update = True
			break

	if update:
		if calendar_event.docstatus == 1:
			calendar_event.cancel()

			new_calendar_event = frappe.copy_doc(calendar_event)
			new_calendar_event.update(updated_event)
			new_calendar_event.flags.pulled_from_google_calendar = True
			new_calendar_event.insert(ignore_permissions=True)
			new_calendar_event.submit()

		elif calendar_event.docstatus == 0:
			calendar_event.update(updated_event)
			calendar_event.flags.pulled_from_google_calendar = True
			calendar_event.save()

def cancel_event_in_calendar(account, event):
	# If any synced Google Calendar Event is cancelled, then close the Event
	add_comment = False
	if frappe.db.exists("Item Booking", {"google_calendar_id": account.google_calendar_id, \
		"google_calendar_event_id": event.get("id"), "docstatus": 1}):
		booking = frappe.get_doc("Item Booking", {"google_calendar_id": account.google_calendar_id, \
			"google_calendar_event_id": event.get("id"), "docstatus": 1})
		booking.flags.pulled_from_google_calendar = True
		booking.cancel()
		add_comment = True


	if frappe.db.exists("Item Booking", {"google_calendar_id": account.google_calendar_id, \
		"google_calendar_event_id": event.get("id"), "docstatus": 0}):
		booking = frappe.get_doc("Item Booking", {"google_calendar_id": account.google_calendar_id, \
			"google_calendar_event_id": event.get("id"), "docstatus": 0})

		try:
			booking.flags.pulled_from_google_calendar = True
			booking.delete
			add_comment = False
		except frappe.LinkExistsError:
			# Try to delete event, but only if it has no links
			add_comment = True
			pass

	if add_comment:
		frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Item Booking",
			"reference_name": booking.get("name"),
			"content": " {0}".format(_("- Event deleted from Google Calendar.")),
		}).insert(ignore_permissions=True)


def insert_event_in_google_calendar(doc, method=None):
	"""
		Insert Events in Google Calendar if sync_with_google_calendar is checked.
	"""
	if not frappe.db.exists("Google Calendar", {"name": doc.google_calendar}) \
		or doc.flags.pulled_from_google_calendar or not doc.sync_with_google_calendar:
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	event = {
		"summary": doc.title,
		"description": doc.notes,
		"sync_with_google_calendar": 1,
		"recurrence": [doc.rrule] if doc.rrule else None
	}
	event.update(format_date_according_to_google_calendar(doc.get("all_day", 0), \
		get_datetime(doc.starts_on), get_datetime(doc.ends_on)))

	try:
		event = google_calendar.events().insert(calendarId=doc.google_calendar_id, body=event).execute()
		doc.google_calendar_event_id = event.get("id")
		frappe.publish_realtime('event_synced',_("Event Synced with Google Calendar."), user=frappe.session.user)
		frappe.msgprint(_("Event Synced with Google Calendar."))
		return doc
	except HttpError as err:
		frappe.throw(_("Google Calendar - Could not insert event in Google Calendar {0}, error code {1}."\
			).format(account.name, err.resp.status))

def update_event_in_google_calendar(doc, method=None):
	"""
		Updates Events in Google Calendar if any existing event is modified in Dokos Calendar
	"""
	# Workaround to avoid triggering update when Event is being inserted since
	# creation and modified are same when inserting doc
	if not frappe.db.exists("Google Calendar", {"name": doc.google_calendar}) or \
		doc.modified == doc.creation or not doc.sync_with_google_calendar or doc.flags.pulled_from_google_calendar:
		return

	if doc.sync_with_google_calendar and not doc.google_calendar_event_id:
		# If sync_with_google_calendar is checked later, then insert the event rather than updating it.
		insert_event_in_google_calendar(doc)
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	try:
		event = google_calendar.events().get(calendarId=doc.google_calendar_id, \
			eventId=doc.google_calendar_event_id).execute()
		event["summary"] = doc.title
		event["description"] = doc.notes
		event["recurrence"] = [doc.rrule] if doc.rrule else None
		event["status"] = "cancelled" if doc.docstatus == 2 else "confirmed"
		event.update(format_date_according_to_google_calendar(doc.get("all_day", 0), \
			get_datetime(doc.starts_on), get_datetime(doc.ends_on)))

		google_calendar.events().update(calendarId=doc.google_calendar_id, \
			eventId=doc.google_calendar_event_id, body=event).execute()
		frappe.msgprint(_("Event Synced with Google Calendar."))
	except HttpError as err:
		frappe.throw(_("Google Calendar - Could not update Event {0} in Google Calendar, error code {1}."\
			).format(doc.name, err.resp.status))

def delete_event_in_google_calendar(doc, method=None):
	"""
		Delete Events from Google Calendar if Item Booking is deleted.
	"""

	if not frappe.db.exists("Google Calendar", {"name": doc.google_calendar}) or \
		doc.flags.pulled_from_google_calendar:
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	try:
		event = google_calendar.events().get(calendarId=doc.google_calendar_id, \
			eventId=doc.google_calendar_event_id).execute()
		event["recurrence"] = None
		event["status"] = "cancelled"

		google_calendar.events().update(calendarId=doc.google_calendar_id, \
			eventId=doc.google_calendar_event_id, body=event).execute()
	except HttpError as err:
		frappe.msgprint(_("Google Calendar - Could not delete Event {0} from Google Calendar, error code {1}."\
			).format(doc.name, err.resp.status))
