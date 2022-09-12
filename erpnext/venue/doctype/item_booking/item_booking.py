# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import calendar
import datetime
import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.desk.calendar import process_recurring_events
from frappe.integrations.doctype.google_calendar.google_calendar import (
	format_date_according_to_google_calendar,
	get_google_calendar_object,
	get_timezone_naive_datetime,
)
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import (
	add_days,
	add_to_date,
	cint,
	date_diff,
	flt,
	fmt_money,
	get_datetime,
	get_time,
	getdate,
	now,
	now_datetime,
	time_diff_in_minutes,
)
from frappe.utils.user import is_system_user, is_website_user
from googleapiclient.errors import HttpError

from erpnext.accounts.party import get_party_account_currency
from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import (
	get_shopping_cart_settings,
)
from erpnext.e_commerce.shopping_cart.cart import get_cart_quotation, get_party
from erpnext.e_commerce.shopping_cart.product_info import get_product_info_for_website
from erpnext.setup.utils import get_exchange_rate
from erpnext.utilities.product import get_price
from erpnext.venue.utils import get_linked_customers


class ItemBooking(Document):
	def before_insert(self):
		if self.parent_item_booking:
			self.google_calendar = self.google_calendar_id = None

	def validate(self):
		self.set_title()

		if self.sync_with_google_calendar and not self.google_calendar:
			self.google_calendar = frappe.db.get_value("Item", self.item, "google_calendar")

		if self.google_calendar and not self.google_calendar_id:
			self.google_calendar_id = frappe.db.get_value(
				"Google Calendar", self.google_calendar, "google_calendar_id"
			)

		if isinstance(self.rrule, list) and self.rrule > 1:
			self.rrule = self.rrule[0]

		if get_datetime(self.starts_on) > get_datetime(self.ends_on):
			frappe.throw(_("Please make sure the end time is greater than the start time"))

		if not self.color:
			self.color = frappe.db.get_value("Item", self.item, "calendar_color")

		if not (self.party_type and self.party_name) and self.user:
			self.party_type, self.party_name = get_corresponding_party(self.user)

		self.check_overlaps()

	def check_overlaps(self):
		overlaps = frappe.db.sql(
			f"""
			SELECT ib.name
			FROM `tabItem Booking` as ib
			WHERE
			(
				(ib.starts_on BETWEEN {frappe.db.escape(add_to_date(self.starts_on, seconds=1))} AND {frappe.db.escape(self.ends_on)})
				OR (ib.ends_on BETWEEN {frappe.db.escape(add_to_date(self.starts_on, seconds=1))} AND {frappe.db.escape(self.ends_on)})
				OR (
					ib.starts_on <= {frappe.db.escape(add_to_date(self.starts_on, seconds=1))}
					AND ib.ends_on >= {frappe.db.escape(self.ends_on)}
				)
			)
			AND ib.item={frappe.db.escape(self.item)}
			AND ib.status!='Cancelled'
			AND ib.name!={frappe.db.escape(self.name)}
		"""
		)

		simultaneous_bookings_allowed = (
			frappe.db.get_value("Item", self.item, "simultaneous_bookings_allowed")
			if frappe.db.get_single_value("Venue Settings", "enable_simultaneous_booking")
			else 0
		)
		no_overlap_per_item = frappe.db.get_single_value("Venue Settings", "no_overlap_per_item")

		if overlaps and not simultaneous_bookings_allowed and no_overlap_per_item:
			frappe.throw(
				_(
					"An existing item booking for this item is overlapping with this document. Please change the dates to register this document of change your settings in Venue Settings."
				)
			)

		elif overlaps and len(overlaps) >= cint(simultaneous_bookings_allowed) and no_overlap_per_item:
			frappe.throw(
				_("The maximum number of simultaneous bookings allowed for this item has been reached.")
			)

		elif overlaps and not simultaneous_bookings_allowed:
			frappe.publish_realtime("booking_overlap")

	def set_title(self):
		if self.meta.get_field("title").hidden or not self.title:
			self.title = self.item_name or ""
			if self.user:
				user_name = frappe.db.get_value("User", self.user, "full_name")
				self.title += " - " + (user_name or self.user)

			elif self.party_name and self.party_type:
				self.title += " - " + frappe.get_doc(self.party_type, self.party_name).get_title() or ""

	def set_status(self, status):
		self.db_set("status", status, update_modified=True, notify=True)
		for child in frappe.get_all(
			"Item Booking", filters=dict(parent_item_booking=self.name), pluck="name"
		):
			frappe.get_doc("Item Booking", child).set_status(status)

	def on_update(self):
		self.synchronize_child_bookings()

		doc_before_save = self.get_doc_before_save()
		if doc_before_save:
			for field in ("status", "starts_on", "ends_on", "party_name"):
				if doc_before_save.get(field) != self.get(field):
					self.delete_linked_credit_usage()

	def delete_linked_credit_usage(self):
		for doc in frappe.get_all(
			"Booking Credit Usage Reference",
			filters={"reference_doctype": "Item Booking", "reference_document": self.name},
			pluck="booking_credit_usage",
		):
			doc = frappe.get_doc("Booking Credit Usage", doc)
			doc.flags.ignore_permissions = True
			doc.cancel()
			doc.delete()

	def synchronize_child_bookings(self):
		def update_child(item, childname=None):
			child = (
				frappe.get_doc("Item Booking", childname) if childname else frappe.new_doc("Item Booking")
			)
			child.update(
				{
					key: value
					for key, value in frappe.copy_doc(self).as_dict().items()
					if (value is not None and not key.startswith("__"))
				}
			)
			child.item = item
			child.parent_item_booking = self.name
			child.save()

		if frappe.db.exists("Product Bundle", dict(new_item_code=self.item)):
			doc = frappe.get_doc("Product Bundle", dict(new_item_code=self.item))
			for item in doc.items:
				childnames = frappe.db.get_all(
					"Item Booking", dict(item=item.item_code, parent_item_booking=self.name), pluck="name"
				)
				for childname in childnames:
					update_child(item.item_code, childname)

				if not childnames:
					for dummy in range(int(item.qty)):
						update_child(item.item_code)

		elif frappe.db.exists("Item Booking", dict(parent_item_booking=self.name)):
			for child in frappe.get_all(
				"Item Booking", filters=dict(parent_item_booking=self.name), fields=["name", "item"]
			):
				update_child(child.item, child.name)


def get_list_context(context=None):
	allow_event_cancellation = frappe.db.get_single_value(
		"Venue Settings", "allow_event_cancellation"
	)
	context.update(
		{
			"show_sidebar": True,
			"show_search": True,
			"no_breadcrumbs": True,
			"title": _("Bookings"),
			"get_list": get_bookings_list,
			"row_template": "templates/includes/item_booking/item_booking_row.html",
			"can_cancel": allow_event_cancellation,
			"cancellation_delay": cint(frappe.db.get_single_value("Venue Settings", "cancellation_delay"))
			/ 60
			if allow_event_cancellation
			else 0,
			"header_action": frappe.render_template(
				"templates/includes/item_booking/item_booking_list_action.html", {}
			),
		}
	)


def get_bookings_list(doctype, txt, filters, limit_start, limit_page_length=20, order_by=None):
	from frappe.www.list import get_list

	user = frappe.session.user
	contact = frappe.db.get_value("Contact", {"user": user}, "name")
	customer = None
	or_filters = []

	if contact:
		contact_doc = frappe.get_doc("Contact", contact)
		customer = contact_doc.get_link_for("Customer")

	if is_website_user() or is_system_user(user):
		if not filters:
			filters = []

		or_filters.append({"user": user, "party_name": customer})

	return get_list(
		doctype,
		txt,
		filters,
		limit_start,
		limit_page_length,
		ignore_permissions=False,
		or_filters=or_filters,
		order_by="starts_on desc",
	)


@frappe.whitelist()
def get_bookings_list_for_map(start, end):
	bookings_list = _get_events(getdate(start), getdate(end), user=frappe.session.user)

	return [
		dict(
			start=x.starts_on,
			end=x.ends_on,
			title=x.item_name,
			status=x.status,
			id=x.name,
			backgroundColor="darkgray"
			if x.ends_on < frappe.utils.now_datetime()
			else (
				"#ff4d4d" if x.status == "Cancelled" else ("#6195ff" if x.status == "Confirmed" else "#ff7846")
			),
			borderColor="darkgray",
		)
		for x in bookings_list
	]


@frappe.whitelist()
def update_linked_transaction(transaction_type, line_item, item_booking):
	return frappe.db.set_value(f"{transaction_type} Item", line_item, "item_booking", item_booking)


@frappe.whitelist()
def get_transactions_items(transaction_type, transactions):
	transactions = frappe.parse_json(transactions)
	output = []
	for transaction in transactions:
		doc = frappe.get_doc(transaction_type, transaction)
		output.extend(doc.items)

	return output


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
	return booking.set_status("Cancelled")


@frappe.whitelist(allow_guest=True)
def get_item_uoms(item_code):
	return {
		"uoms": frappe.get_all(
			"UOM Conversion Detail",
			filters={"parent": item_code},
			fields=["distinct uom"],
			order_by="idx desc",
			as_list=1,
		),
		"sales_uom": frappe.get_cached_value("Item", item_code, "sales_uom"),
	}


@frappe.whitelist(allow_guest=True)
def get_item_price(item_code, uom):
	cart_settings = get_shopping_cart_settings()

	if not cart_settings.enabled:
		return frappe._dict()

	contact = frappe.db.get_value("Contact", {"user": frappe.session.user})

	cart_quotation = None
	if contact:
		dummy, quotation = get_cart_quotation()
		if quotation:
			cart_quotation = frappe.db.get_value(
				"Quotation", quotation[0].name, ["selling_price_list", "grand_total", "currency"], as_dict=True
			)

	price = get_price(
		item_code=item_code,
		price_list=cart_quotation.selling_price_list if cart_quotation else cart_settings.price_list,
		customer_group=cart_settings.default_customer_group,
		company=cart_settings.company,
		uom=uom,
	)

	return {
		"item_name": frappe.db.get_value("Item", item_code, "item_name"),
		"price": price,
		"total": fmt_money(
			(cart_quotation.grand_total or 0) if cart_quotation else 0,
			currency=cart_quotation.currency if cart_quotation else price.get("currency"),
		),
	}


@frappe.whitelist()
def book_new_slot(**kwargs):
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Item Booking",
				"item": kwargs.get("item"),
				"starts_on": kwargs.get("start"),
				"ends_on": kwargs.get("end"),
				"user": kwargs.get("user"),
				"status": kwargs.get("status") or "In cart",
				"event": kwargs.get("event"),
				"all_day": kwargs.get("all_day") or 0,
				"uom": kwargs.get("uom"),
				"sync_with_google_calendar": kwargs.get("sync_with_google_calendar")
				or frappe.db.get_single_value("Venue Settings", "sync_with_google_calendar"),
			}
		).insert(ignore_permissions=True)

		return doc
	except Exception:
		if frappe.db.get_value("User", frappe.session.user, "user_type") != "System User":
			frappe.log_error(_("New item booking error"))


@frappe.whitelist()
def remove_booked_slot(name):
	try:
		for dt in ["Quotation", "Sales Order"]:
			linked_docs = frappe.get_all(
				f"{dt} Item", filters={"item_booking": name, "parenttype": dt}, fields=["name", "parent"]
			)
			for d in linked_docs:
				doc = frappe.get_doc(dt, d.get("parent"))
				if len(doc.items) > 1:
					doc.items = [i for i in doc.items if i.item_booking != name]
					doc.flags.ignore_permissions = True
					doc.save()
				else:
					frappe.delete_doc(dt, doc.name, ignore_permissions=True, force=True)

		return frappe.delete_doc("Item Booking", name, ignore_permissions=True, force=True)
	except frappe.TimestampMismatchError:
		frappe.get_doc("Item Booking", name).reload()
		remove_booked_slot(name)


@frappe.whitelist()
def get_booked_slots(quotation=None, uom=None, item_code=None):
	if not quotation and not frappe.session.user == "Guest":
		dummy, quotation = _get_cart_quotation()

	if not quotation:
		return []

	filters = dict(parenttype="Quotation", parent=quotation[0].name)
	if uom:
		filters["uom"] = uom

	if item_code:
		filters["item_code"] = item_code

	return frappe.get_all("Quotation Item", filters=filters, fields=["item_booking as name"])


@frappe.whitelist(allow_guest=True)
def get_detailed_booked_slots(quotation=None, uom=None, item_code=None):
	slots = [x.name for x in get_booked_slots(quotation, uom, item_code) if x.name]

	return frappe.get_all(
		"Item Booking", filters={"name": ("in", slots)}, fields=["name", "starts_on", "ends_on"]
	)


@frappe.whitelist()
def reset_all_booked_slots():
	slots = get_booked_slots()
	for slot in slots:
		remove_booked_slot(slot.get("name"))

	return slots


@frappe.whitelist(allow_guest=True)
def get_available_item(item, start, end):
	alternative_items = frappe.get_all(
		"Item",
		filters={"show_in_website": 1, "enable_item_booking": 1, "item_code": ["!=", item]},
		fields=[
			"name",
			"item_name",
			"route",
			"website_image",
			"image",
			"description",
			"website_content",
		],
	)

	available_items = []
	for alternative_item in alternative_items:
		availabilities = get_availabilities(alternative_item.name, start, end) or []
		if len(availabilities):
			available_items.append(alternative_item)

	result = []
	for available_item in available_items:
		product_info = get_product_info_for_website(available_item.name)
		if (
			product_info.product_info
			and product_info.product_info.get("price")
			and (
				product_info.cart_settings.get("allow_items_not_in_stock")
				or product_info.product_info.get("in_stock")
			)
		):
			result.append(available_item)

	return result


# TODO: refactor with a class and add an option to get monthly availabilities
@frappe.whitelist(allow_guest=True)
def get_availabilities(item, start, end, uom=None, user=None):
	return ItemBookingAvailabilities(
		item=item, start=start, end=end, uom=uom, user=user
	).get_available_slots()


class ItemBookingAvailabilities:
	def __init__(self, *args, **kwargs):
		self.item = kwargs.get("item")
		self.start = kwargs.get("start")
		self.end = kwargs.get("end")
		self.init = (
			datetime.datetime.strptime(self.start, "%Y-%m-%d")
			if type(self.start) == str
			else get_datetime(self.start)
		)
		self.finish = (
			datetime.datetime.strptime(self.end, "%Y-%m-%d")
			if type(self.end) == str
			else get_datetime(self.end)
		)
		self.user = kwargs.get("user") or frappe.session.user

		self.item_doc = frappe.db.get_value(
			"Item",
			self.item,
			["name", "sales_uom", "enable_item_booking", "simultaneous_bookings_allowed"],
			as_dict=True,
		)

		self.uom = kwargs.get("uom") or self.item_doc.sales_uom
		self.duration = get_uom_in_minutes(self.uom)

	def get_available_slots(self):
		if not self.item_doc.enable_item_booking or not self.duration:
			return []

		output = []
		for dt in daterange(self.init, self.finish):
			calendar_availability = self._check_availability(dt)
			if calendar_availability:
				output.extend(calendar_availability)

		return output

	def _check_availability(self, date):
		date = getdate(date)
		day = calendar.day_name[date.weekday()]

		item_calendar = get_item_calendar(self.item, self.uom)

		availability = []
		schedules = []
		if item_calendar.get("calendar"):
			schedule_for_the_day = filter(lambda x: x.day == day, item_calendar.get("calendar"))
			for line in schedule_for_the_day:
				start = get_datetime(now())
				if datetime.datetime.combine(date, get_time(line.end_time)) > start:
					if datetime.datetime.combine(date, get_time(line.start_time)) > start:
						start = datetime.datetime.combine(date, get_time(line.start_time))

					schedules.append(
						{"start": start, "end": datetime.datetime.combine(date, get_time(line.end_time))}
					)

			if schedules:
				availability.extend(self._get_availability_from_schedule(schedules))

		return availability

	def _get_availability_from_schedule(self, schedules):
		available_slots = []
		for line in schedules:
			line = frappe._dict(line)
			booked_items = _get_events(line.get("start"), line.get("end"), self.item_doc)
			scheduled_items = []
			for event in booked_items:
				if (
					get_datetime(event.get("starts_on")) >= line.get("start")
					and get_datetime(event.get("starts_on")) <= line.get("end")
				) or get_datetime(event.get("ends_on")) >= line.get("start"):
					scheduled_items.append(event)

			slots = self._find_available_slot(line, scheduled_items)
			available_slots_ids = [s.get("id") for s in available_slots]

			for slot in slots:
				if slot.get("id") not in available_slots_ids:
					available_slots.append(slot)

		return available_slots

	def _find_available_slot(self, line, scheduled_items):
		slots = []
		output = []
		user_scheduled_items = [x for x in scheduled_items if x.get("user") == self.user]

		simultaneous_booking_allowed = frappe.get_cached_value(
			"Venue Settings", None, "enable_simultaneous_booking"
		)
		if simultaneous_booking_allowed:
			scheduled_items = self.check_simultaneaous_bookings(scheduled_items)

		slots.extend(
			self._get_all_slots(
				line,
				simultaneous_booking_allowed,
				scheduled_items,
			)
		)

		if not slots and not scheduled_items:
			slots.extend(self._get_all_slots(line, simultaneous_booking_allowed))

		for slot in slots:
			output.append(self.get_available_dict(slot))

		for scheduled_item in user_scheduled_items:
			added = False
			for out in output:
				if (
					out.get("start") == scheduled_item.get("starts_on").isoformat()
					and out.get("end") == scheduled_item.get("ends_on").isoformat()
				):
					out.id = scheduled_item.get("name")
					out.status = "selected"
					out.number += 1
					added = True

				elif getdate(out.get("start")) == getdate(scheduled_item.get("starts_on")) or getdate(
					out.get("end")
				) == getdate(scheduled_item.get("ends_on")):
					out.color = "var(--primary-color)"

			if not added:
				out = self.get_available_dict(scheduled_item, "selected")
				out.color = "var(--primary-color)"
				out.number += 1
				output.append(out)

		return output

	def check_simultaneaous_bookings(self, scheduled_items):
		import itertools
		from operator import itemgetter

		simultaneous_bookings = self.item_doc.get("simultaneous_bookings_allowed")
		if simultaneous_bookings > 1:
			sorted_schedule = sorted(scheduled_items, key=itemgetter("starts_on"))
			for dummy, group in itertools.groupby(sorted_schedule, key=lambda x: x["starts_on"]):
				grouped_sch = [x.get("name") for x in list(group)]
				if len(grouped_sch) == simultaneous_bookings:
					scheduled_items = [x for x in scheduled_items if x.get("name") not in grouped_sch[:-1]]
				elif len(grouped_sch) < simultaneous_bookings:
					scheduled_items = [x for x in scheduled_items if x.get("name") not in grouped_sch]

		return scheduled_items

	def _get_all_slots(self, line, simultaneous_booking_allowed, scheduled_items=None):
		interval = int(datetime.timedelta(minutes=cint(self.duration)).total_seconds() / 60)
		slots = sorted([(line.start, line.start)] + [(line.end, line.end)])
		if not scheduled_items:
			scheduled_items = []

		if simultaneous_booking_allowed:
			vanilla_start_times = []
			for start, end in ((slots[i][0], slots[i + 1][0]) for i in range(len(slots) - 1)):
				while start + timedelta(minutes=interval) <= end:
					vanilla_start_times.append(start)
					start += timedelta(minutes=interval)

		current_schedule = []
		for scheduled_item in scheduled_items:
			try:
				if get_datetime(scheduled_item.get("starts_on")) < line.get("start"):
					current_schedule.append(
						(get_datetime(line.get("start")), get_datetime(scheduled_item.get("ends_on")))
					)
				elif get_datetime(scheduled_item.get("starts_on")) < line.get("end"):
					current_schedule.append(
						(get_datetime(scheduled_item.get("starts_on")), get_datetime(scheduled_item.get("ends_on")))
					)
			except Exception:
				frappe.log_error(_("Slot availability error"))

		if current_schedule:
			sorted_schedule = list(reduced(sorted(current_schedule, key=lambda x: x[0])))
			slots = sorted([(line.start, line.start)] + sorted_schedule + [(line.end, line.end)])

		free_slots = []
		for start, end in ((slots[i][1], slots[i + 1][0]) for i in range(len(slots) - 1)):
			while start + timedelta(minutes=interval) <= end:
				if simultaneous_booking_allowed:
					if start not in vanilla_start_times:
						vanilla_start = [x for x in vanilla_start_times if start + timedelta(minutes=interval) <= x]
						if vanilla_start:
							start = vanilla_start[0]
				free_slots.append({"starts_on": start, "ends_on": start + timedelta(minutes=interval)})
				start += timedelta(minutes=interval)

		return free_slots

	def get_available_dict(self, slot, status=None):
		"""
		Status can be:
		        - available
		        - selected
		"""
		return frappe._dict(
			{
				"start": slot.get("starts_on").isoformat(),
				"end": slot.get("ends_on").isoformat(),
				"id": slot.get("name") or frappe.generate_hash(length=8),
				"status": status or "available",
				"number": 0,
				"total_available": self.item_doc.get("simultaneous_bookings_allowed"),
				"display": "background",
				"color": None,
				"allDay": 1,
			}
		)


def _get_events(start, end, item=None, user=None):
	conditions = ""
	if item:
		conditions += " AND item='{0}' ".format(frappe.db.escape(item.name))
	if user:
		conditions += " AND user='{0}' ".format(user)

	events = frappe.db.sql(
		"""
		SELECT starts_on,
				ends_on,
				item_name,
				name,
				repeat_this_event,
				rrule,
				user,
				status
		FROM `tabItem Booking`
		WHERE (
				(
					(date(starts_on) BETWEEN date(%(start)s) AND date(%(end)s))
					OR (date(ends_on) BETWEEN date(%(start)s) AND date(%(end)s))
					OR (
						date(starts_on) <= date(%(start)s)
						AND date(ends_on) >= date(%(end)s)
					)
				)
				OR (
					date(starts_on) <= date(%(start)s)
					AND repeat_this_event=1
					AND coalesce(repeat_till, '3000-01-01') > date(%(start)s)
				)
			)
		AND status!="Cancelled"
		{conditions}
		ORDER BY starts_on""".format(
			conditions=conditions
		),
		{"start": start, "end": end},
		as_dict=1,
	)

	result = []

	for event in events:
		result.append(event)
		if event.get("repeat_this_event") == 1:
			result.extend(
				process_recurring_events(event, now_datetime(), end, "starts_on", "ends_on", "rrule")
			)

	return result


@frappe.whitelist(allow_guest=True)
def get_item_calendar(item=None, uom=None):
	if not uom:
		uom = frappe.get_cached_value("Item", item, "sales_uom")

	calendars = frappe.get_all(
		"Item Booking Calendar", fields=["name", "item", "uom", "calendar_type"]
	)
	for filters in [
		dict(item=item, uom=uom),
		dict(item=item, uom=None),
		dict(item=None, uom=uom),
		dict(item=None, uom=None),
	]:
		filtered_calendars = [
			x
			for x in calendars
			if (x.get("item") == filters.get("item") or x.get("item") == "")
			and (x.get("uom") == filters.get("uom") or x.get("uom") == "")
		]
		if filtered_calendars:
			return {
				"type": filtered_calendars[0].calendar_type or "Daily",
				"calendar": frappe.get_all(
					"Item Booking Calendars",
					filters={"parent": filtered_calendars[0].name, "parenttype": "Item Booking Calendar"},
					fields=["start_time", "end_time", "day"],
				),
				"name": filtered_calendars[0].name,
			}

	return {"type": "Daily", "calendar": [], "name": None}


def get_uom_in_minutes(uom=None):
	minute_uom = frappe.db.get_single_value("Venue Settings", "minute_uom")
	if uom == minute_uom:
		return 1

	return (
		frappe.db.get_value("UOM Conversion Factor", dict(from_uom=uom, to_uom=minute_uom), "value") or 0
	)


def get_sales_qty(item, start, end):
	minute_uom = frappe.db.get_single_value("Venue Settings", "minute_uom")
	sales_uom = frappe.get_cached_value("Item", item, "sales_uom") or frappe.get_cached_value(
		"Item", item, "stock_uom"
	)
	duration = time_diff_in_minutes(end, start)

	if sales_uom == minute_uom:
		return duration

	conversion_factor = (
		frappe.db.get_value(
			"UOM Conversion Factor", dict(from_uom=sales_uom, to_uom=minute_uom), "value"
		)
		or 1
	)

	return flt(duration) / flt(conversion_factor)


def daterange(start_date, end_date):
	if start_date < get_datetime(now()):
		start_date = datetime.datetime.now().replace(
			hour=0, minute=0, second=0, microsecond=0
		) + datetime.timedelta(days=1)
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


def confirm_linked_item_bookings(doc, method):
	confirm_after_payment = cint(
		frappe.db.get_single_value("Venue Settings", "confirm_booking_after_payment")
	)
	for item in doc.items:
		if item.item_booking:
			slot = frappe.get_doc("Item Booking", item.item_booking)
			slot.flags.ignore_permissions = True
			slot.set_status("Not confirmed" if confirm_after_payment else "Confirmed")


def clear_draft_bookings():
	drafts = frappe.get_all(
		"Item Booking", filters={"status": "In cart"}, fields=["name", "modified"]
	)
	clearing_duration = frappe.db.get_value(
		"Venue Settings", None, "clear_item_booking_draft_duration"
	)

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
		company_currency = frappe.get_cached_value("Company", quotation.company, "default_currency")

		if quotation.quotation_to == "Customer" and quotation.party_name:
			party_account_currency = get_party_account_currency(
				"Customer", quotation.party_name, quotation.company
			)
		else:
			party_account_currency = company_currency

		quotation.currency = party_account_currency or company_currency

		if company_currency == quotation.currency:
			exchange_rate = 1
		else:
			exchange_rate = get_exchange_rate(
				quotation.currency, company_currency, quotation.transaction_date, args="for_selling"
			)

		quotation.conversion_rate = exchange_rate

		# add item
		quotation.append(
			"items",
			{
				"item_code": source.item,
				"qty": get_sales_qty(source.item, source.starts_on, source.ends_on),
				"uom": frappe.get_cached_value("Item", source.item, "sales_uom"),
				"item_booking": source.name,
			},
		)

		# get default taxes
		taxes = get_default_taxes_and_charges(
			"Sales Taxes and Charges Template", company=quotation.company
		)
		if taxes.get("taxes"):
			quotation.update(taxes)

		quotation.run_method("set_missing_values")
		quotation.run_method("calculate_taxes_and_totals")

	doclist = get_mapped_doc(
		"Item Booking",
		source_name,
		{"Item Booking": {"doctype": "Quotation", "field_map": {"party_type": "quotation_to"}}},
		target_doc,
		set_missing_values,
	)

	return doclist


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
	def set_missing_values(source, target):
		from erpnext.controllers.accounts_controller import get_default_taxes_and_charges

		sales_order = frappe.get_doc(target)
		sales_order.order_type = "Maintenance"
		company_currency = frappe.get_cached_value("Company", sales_order.company, "default_currency")

		party_account_currency = get_party_account_currency(
			"Customer", sales_order.customer, sales_order.company
		)

		sales_order.currency = party_account_currency or company_currency

		if company_currency == sales_order.currency:
			exchange_rate = 1
		else:
			exchange_rate = get_exchange_rate(
				sales_order.currency, company_currency, sales_order.transaction_date, args="for_selling"
			)

		sales_order.conversion_rate = exchange_rate

		# add item
		sales_order.append(
			"items",
			{
				"item_code": source.item,
				"qty": get_sales_qty(source.item, source.starts_on, source.ends_on),
				"uom": frappe.get_cached_value("Item", source.item, "sales_uom"),
				"item_booking": source.name,
			},
		)

		# get default taxes
		taxes = get_default_taxes_and_charges(
			"Sales Taxes and Charges Template", company=sales_order.company
		)
		if taxes.get("taxes"):
			sales_order.update(taxes)

		sales_order.run_method("set_missing_values")
		sales_order.run_method("calculate_taxes_and_totals")

	doclist = get_mapped_doc(
		"Item Booking",
		source_name,
		{"Item Booking": {"doctype": "Sales Order", "field_map": {"party_name": "customer"}}},
		target_doc,
		set_missing_values,
	)

	return doclist


def get_calendar_item(account):
	return frappe.db.get_value(
		"Item", dict(google_calendar=account.name, disabled=0), ["item_code", "calendar_color"]
	)


def insert_event_to_calendar(account, event, recurrence=None):
	"""
	Inserts event in Dokos Calendar during Sync
	"""
	start = event.get("start")
	end = event.get("end")
	item, color = get_calendar_item(account)

	calendar_event = {
		"doctype": "Item Booking",
		"item": item,
		"color": color,
		"notes": event.get("description"),
		"sync_with_google_calendar": 1,
		"google_calendar": account.name,
		"google_calendar_id": account.google_calendar_id,
		"google_calendar_event_id": event.get("id"),
		"rrule": recurrence,
		"starts_on": get_datetime(start.get("date"))
		if start.get("date")
		else get_timezone_naive_datetime(start),
		"ends_on": get_datetime(end.get("date"))
		if end.get("date")
		else get_timezone_naive_datetime(end),
		"all_day": 1 if start.get("date") else 0,
		"repeat_this_event": 1 if recurrence else 0,
		"status": "Confirmed",
	}
	doc = frappe.get_doc(calendar_event)
	doc.flags.pulled_from_google_calendar = True
	doc.insert(ignore_permissions=True)


def update_event_in_calendar(account, event, recurrence=None):
	"""
	Updates Event in Dokos Calendar if any existing Google Calendar Event is updated
	"""
	start = event.get("start")
	end = event.get("end")

	calendar_event = frappe.get_doc("Item Booking", {"google_calendar_event_id": event.get("id")})
	item, _ = get_calendar_item(account)

	updated_event = {
		"item": item,
		"notes": event.get("description"),
		"rrule": recurrence,
		"starts_on": get_datetime(start.get("date"))
		if start.get("date")
		else get_timezone_naive_datetime(start),
		"ends_on": get_datetime(end.get("date"))
		if end.get("date")
		else get_timezone_naive_datetime(end),
		"all_day": 1 if start.get("date") else 0,
		"repeat_this_event": 1 if recurrence else 0,
		"status": "Confirmed",
	}

	update = False
	for field in updated_event:
		if field == "rrule" and recurrence:
			update = calendar_event.get(field) is None or (
				set(calendar_event.get(field).split(";")) != set(updated_event.get(field).split(";"))
			)
		else:
			update = str(calendar_event.get(field)) != str(updated_event.get(field))
		if update:
			break

	if update:
		calendar_event.update(updated_event)
		calendar_event.flags.pulled_from_google_calendar = True
		calendar_event.save()


def cancel_event_in_calendar(account, event):
	# If any synced Google Calendar Event is cancelled, then close the Event
	add_comment = False

	if frappe.db.exists(
		"Item Booking",
		{"google_calendar_id": account.google_calendar_id, "google_calendar_event_id": event.get("id")},
	):
		booking = frappe.get_doc(
			"Item Booking",
			{"google_calendar_id": account.google_calendar_id, "google_calendar_event_id": event.get("id")},
		)

		try:
			booking.flags.pulled_from_google_calendar = True
			booking.delete()
			add_comment = False
		except frappe.LinkExistsError:
			# Try to delete event, but only if it has no links
			add_comment = True

	if add_comment:
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "Item Booking",
				"reference_name": booking.get("name"),
				"content": " {0}".format(_("- Event deleted from Google Calendar.")),
			}
		).insert(ignore_permissions=True)


def insert_event_in_google_calendar(doc, method=None):
	"""
	Insert Events in Google Calendar if sync_with_google_calendar is checked.
	"""
	if (
		not frappe.db.exists("Google Calendar", {"name": doc.google_calendar})
		or doc.flags.pulled_from_google_calendar
		or not doc.sync_with_google_calendar
	):
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	event = {
		"summary": doc.title,
		"description": doc.notes,
		"recurrence": [doc.rrule] if doc.repeat_this_event and doc.rrule else [],
	}
	event.update(
		format_date_according_to_google_calendar(
			doc.get("all_day", 0), get_datetime(doc.starts_on), get_datetime(doc.ends_on)
		)
	)

	try:
		event = google_calendar.events().insert(calendarId=doc.google_calendar_id, body=event).execute()
		doc.db_set("google_calendar_event_id", event.get("id"), update_modified=False)
		frappe.publish_realtime(
			"event_synced", {"message": _("Event Synced with Google Calendar.")}, user=frappe.session.user
		)
	except HttpError as err:
		frappe.msgprint(f'{_("Google Error")}: {json.loads(err.content)["error"]["message"]}')
		frappe.throw(
			_("Google Calendar - Could not insert event in Google Calendar {0}, error code {1}.").format(
				account.name, err.resp.status
			)
		)


def update_event_in_google_calendar(doc, method=None):
	"""
	Updates Events in Google Calendar if any existing event is modified in Dokos Calendar
	"""
	# Workaround to avoid triggering update when Event is being inserted since
	# creation and modified are same when inserting doc
	if (
		not frappe.db.exists("Google Calendar", {"name": doc.google_calendar})
		or doc.modified == doc.creation
		or not doc.sync_with_google_calendar
		or doc.flags.pulled_from_google_calendar
	):
		return

	if doc.sync_with_google_calendar and not doc.google_calendar_event_id:
		# If sync_with_google_calendar is checked later, then insert the event rather than updating it.
		insert_event_in_google_calendar(doc)
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	try:
		event = (
			google_calendar.events()
			.get(calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id)
			.execute()
		)
		event["summary"] = doc.title
		event["description"] = doc.notes
		event["recurrence"] = [doc.rrule] if doc.repeat_this_event and doc.rrule else []
		event["status"] = "cancelled" if doc.status == "Cancelled" else "confirmed"
		event.update(
			format_date_according_to_google_calendar(
				doc.get("all_day", 0), get_datetime(doc.starts_on), get_datetime(doc.ends_on)
			)
		)

		google_calendar.events().update(
			calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id, body=event
		).execute()
		frappe.publish_realtime(
			"event_synced", {"message": _("Event Synced with Google Calendar.")}, user=frappe.session.user
		)
	except HttpError as err:
		frappe.msgprint(f'{_("Google Error")}: {json.loads(err.content)["error"]["message"]}')
		frappe.throw(
			_("Google Calendar - Could not update Event {0} in Google Calendar, error code {1}.").format(
				doc.name, err.resp.status
			)
		)


def delete_event_in_google_calendar(doc, method=None):
	"""
	Delete Events from Google Calendar if Item Booking is deleted.
	"""

	if (
		not frappe.db.exists("Google Calendar", {"name": doc.google_calendar})
		or doc.flags.pulled_from_google_calendar
		or not doc.sync_with_google_calendar
		or not doc.google_calendar_event_id
	):
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	try:
		event = (
			google_calendar.events()
			.get(calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id)
			.execute()
		)
		event["recurrence"] = None
		event["status"] = "cancelled"

		google_calendar.events().update(
			calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id, body=event
		).execute()
	except HttpError as err:
		frappe.msgprint(f'{_("Google Error")}: {json.loads(err.content)["error"]["message"]}')
		frappe.msgprint(
			_("Google Calendar - Could not delete Event {0} from Google Calendar, error code {1}.").format(
				doc.name, err.resp.status
			)
		)


@frappe.whitelist()
def get_corresponding_party(user):
	customers, leads = get_linked_customers(user)
	party_type = party_name = None
	if customers:
		party_type = "Customer"
		party_name = customers[0]

	elif leads:
		party_type = "Lead"
		party_name = leads[0]

	return party_type, party_name


def move_booking_with_event(doc, method):
	doc_before_save = doc.get_doc_before_save()
	if doc_before_save and getdate(doc_before_save.starts_on) != getdate(doc.starts_on):
		days = date_diff(doc.starts_on, doc_before_save.starts_on)
		bookings = frappe.get_all(
			"Item Booking", filters={"event": doc.name}, fields=["name", "starts_on", "ends_on"]
		)

		for booking in bookings:
			doc = frappe.get_doc("Item Booking", booking.name)
			doc.starts_on = add_days(booking.starts_on, days)
			doc.ends_on = add_days(booking.ends_on, days)
			doc.save()


@frappe.whitelist()
def get_booking_count(item=None, starts_on=None, ends_on=None):
	if not (item and starts_on and ends_on):
		return

	simultaneous_bookings_enabled = frappe.db.get_single_value(
		"Venue Settings", "enable_simultaneous_booking"
	)
	slots_left = 0

	if simultaneous_bookings_enabled:
		item_doc = frappe.get_doc("Item", item)
		events = _get_events(getdate(starts_on), getdate(ends_on), item_doc)
		timeslot = (get_datetime(starts_on), get_datetime(ends_on))
		slots_left = (
			cint(item_doc.get("simultaneous_bookings_allowed"))
			- get_simultaneaous_bookings(events, timeslot, item_doc.get("simultaneous_bookings_allowed"))
			- 1
		)

	return slots_left


def get_simultaneaous_bookings(scheduled_items, timeslot, simultaneous_bookings=None):
	import itertools
	from operator import itemgetter

	count = 0
	if cint(simultaneous_bookings) > 1:
		sorted_schedule = sorted(scheduled_items, key=itemgetter("starts_on"))
		for key, group in itertools.groupby(sorted_schedule, key=lambda x: x["starts_on"]):
			group_count = 0
			for slot in group:
				if get_datetime(timeslot[1]) > slot.get("starts_on") and get_datetime(timeslot[0]) < slot.get(
					"ends_on"
				):
					group_count += 1

			count = max(count, group_count)

	return count


def _get_cart_quotation():
	party = get_party()

	return frappe.get_all(
		"Quotation",
		fields=["name"],
		filters={
			"party_name": party.name,
			"contact_email": frappe.session.user,
			"order_type": "Shopping Cart",
			"docstatus": 0,
		},
		order_by="modified desc",
		limit_page_length=1,
	)
