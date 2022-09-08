# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import calendar
import math
from datetime import date, datetime, timedelta
from itertools import chain

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	add_to_date,
	flt,
	get_datetime,
	get_first_day,
	get_first_day_of_week,
	get_last_day,
	get_time,
	get_year_ending,
	getdate,
	now_datetime,
	time_diff_in_minutes,
)

from erpnext.venue.doctype.booking_credit.booking_credit import get_balance
from erpnext.venue.doctype.item_booking.item_booking import get_item_calendar, get_uom_in_minutes
from erpnext.venue.utils import get_linked_customers

ACTION_MAP = {
	"after_insert": "After Insert",
	"on_change": "If Status Changes",
	"on_submit": "On Submit",
	"on_cancel": "On Cancel",
	"on_trash": "On Delete",
}


class BookingCreditRule(Document):
	def on_update(self):
		set_trigger_docs()

	def after_insert(self):
		set_trigger_docs()

	def process_rule(self, doc):
		if self.conditions and not frappe.safe_eval(self.conditions, {"doc": doc}):
			return

		if self.trigger_action == "If Status Changes" and doc.status != self.expected_status:
			return

		return RuleProcessor(self, doc).process()

	def process_timely_rule(self):
		used_docs = frappe.get_all(
			"Booking Credit Usage Reference",
			filters={"reference_doctype": self.trigger_document},
			fields=["reference_document"],
			pluck="reference_document",
		)

		filters = {"name": ("not in", used_docs)} if used_docs else {}

		meta = frappe.get_meta(self.trigger_document)
		if meta.has_field("status"):
			filters.update({"status": ("!=", "Cancelled")})

		if meta.is_submittable:
			filters.update({"docstatus": 1})

		if self.trigger_action == "After Document Start Datetime":
			time_field = self.start_time_field
		else:
			time_field = self.end_time_field

		filters.update(
			{
				time_field: ("<=", now_datetime()),
				self.start_time_field: (">", self.valid_from or self.creation),
			}
		)

		docs = frappe.get_all(self.trigger_document, filters=filters)

		for doc in docs:
			document = frappe.get_doc(self.trigger_document, doc.name)
			self.process_rule(document)


def trigger_credit_rules(doc, method):
	if (
		frappe.flags.in_patch
		or frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard
	):
		return

	filters = {
		"disabled": 0,
		"trigger_document": doc.doctype,
		"trigger_action": ACTION_MAP.get(method),
	}

	if doc.doctype in get_trigger_docs() and frappe.db.get_value("Booking Credit Rule", filters):
		rules = frappe.get_all("Booking Credit Rule", filters=filters)

		for rule in rules:
			frappe.get_doc("Booking Credit Rule", rule.name).process_rule(doc)


def get_trigger_docs():
	trigger_docs = frappe.cache().get_value("booking_credit_documents", _get_booking_credit_documents)
	if not trigger_docs:
		trigger_docs = set_trigger_docs()
	return trigger_docs


def set_trigger_docs():
	trigger_docs = _get_booking_credit_documents()
	frappe.cache().set_value("booking_credit_documents", trigger_docs)
	return trigger_docs


def _get_booking_credit_documents():
	return frappe.get_all("Booking Credit Rule", pluck="trigger_document", distinct=True)


def trigger_after_specific_time():
	rules = frappe.get_all(
		"Booking Credit Rule",
		filters={
			"disabled": 0,
			"trigger_action": ("in", ("After Document Start Datetime", "After Document End Datetime")),
		},
		fields=["name"],
	)

	for rule in rules:
		frappe.get_doc("Booking Credit Rule", rule.name).process_timely_rule()


@frappe.whitelist()
def get_fieldtypes_options(doctype, fieldtypes):
	try:
		fieldtypes = frappe.parse_json(fieldtypes)
	except Exception:
		fieldtypes = fieldtypes

	result = frappe.get_all(
		"DocField",
		filters={"parent": doctype, "fieldtype": ("in", fieldtypes)},
		fields=["fieldname as value", "label"],
	)

	return [{"value": x.value, "label": _(x.label)} for x in result]


@frappe.whitelist()
def get_status_options(doctype):
	options = frappe.get_all(
		"DocField",
		filters={"parent": doctype, "fieldname": "status"},
		fields=["options"],
		pluck="options",
	)

	return [{"label": _(x), "value": x} for x in options[0].split("\n")] if options else ""


@frappe.whitelist()
def get_link_options(doctype, link):
	result = frappe.get_all(
		"DocField",
		filters={"parent": doctype, "fieldtype": "Link", "options": link},
		fields=["fieldname as value", "label"],
	) + frappe.get_all(
		"DocField",
		filters={"parent": doctype, "fieldtype": "Dynamic Link"},
		fields=["fieldname as value", "label"],
	)

	return [{"value": x.value, "label": _(x.label)} for x in result]


@frappe.whitelist()
def get_child_tables(doctype):
	return [
		{"value": x.fieldname, "label": _(x.label)}
		for x in frappe.get_meta(doctype).fields
		if x.fieldtype == "Table"
	]


class RuleProcessor:
	def __init__(self, rule, doc):
		self.rule = rule
		self.doc = doc
		self.user = getattr(doc, self.rule.user_field, None) if self.rule.user_field else None
		self.customer = (
			getattr(doc, self.rule.customer_field, None) if self.rule.customer_field else None
		)
		self.uom = getattr(doc, self.rule.uom_field, None) if self.rule.uom_field else None
		self.qty = self.item = None
		self.start = (
			get_datetime(getattr(doc, self.rule.start_time_field, now_datetime()))
			if self.rule.start_time_field
			else now_datetime()
		)
		self.end = (
			get_datetime(getattr(doc, self.rule.end_time_field, now_datetime()))
			if self.rule.end_time_field
			else now_datetime()
		)
		self.datetime = now_datetime()
		self.duration = time_diff_in_minutes(self.end, self.start) or 1
		self.days = 1

		if getattr(doc, "all_day", None) or getattr(doc, "allDay", None):
			self.start = self.start.replace(hour=0, minute=0, second=0)
			self.end = add_days(self.end, 1).replace(hour=0, minute=0, second=0)
			self.days = (self.end - self.start).days

		self.min_time = None

	def process(self):
		if not self.customer:
			if not self.user:
				return

			customers, dummy = get_linked_customers(self.user)
			if customers:
				self.customer = customers[0]

		if not (self.customer or self.user):
			return

		if self.rule.rule_type == "Booking Credits Deduction":
			self.datetime = get_datetime(self.start)
			self.item = getattr(self.doc, self.rule.item_field, None) if self.rule.item_field else None

			if self.rule.applicable_for and self.check_application_rule(self.doc):
				return

			if self.rule.custom_deduction_rule:
				self.apply_custom_rules()
			else:
				self.apply_standard_rules()

		else:
			self.apply_addition_rules()

	def check_application_rule(self, doc):
		meta = frappe.get_meta(doc.doctype)
		options = [x.options for x in meta.fields]
		if self.rule.applicable_for not in options:
			if self.rule.applicable_for == "Item Group" and "Item" in options:
				fields = [x.fieldname for x in meta.fields if x.options == "Item"]
				for field in fields:
					item_group = frappe.db.get_value("Item", doc.get(field), "item_group")
					return item_group != self.rule.applicable_for_document_type
			elif self.rule.applicable_for == "Customer Group":
				fields = [x.fieldname for x in meta.fields if x.options == "Customer"]
				for field in fields:
					customer_group = frappe.db.get_value("Customer", doc.get(field), "customer_group")
					return customer_group != self.rule.applicable_for_document_type

			return True

		fields = [x.fieldname for x in meta.fields if x.options == self.rule.applicable_for]

		for field in fields:
			if getattr(doc, field, None) == self.rule.applicable_for_document_type:
				return False

		return True

	def apply_addition_rules(self):
		self.datetime = self.get_posting_date()
		recurrences = self.get_recurrence()

		for recurrence in recurrences:
			self.datetime = get_datetime(recurrence)
			self.expiration_date = self.get_expiration_date()

			if self.rule.use_child_table:
				for row in self.doc.get(self.rule.child_table) or []:
					if self.rule.applicable_for and self.check_application_rule(row):
						continue

					self.item = getattr(row, self.rule.item_field, None) if self.rule.item_field else None
					self.uom = getattr(row, self.rule.uom_field, None) if self.rule.uom_field else None
					self.qty = getattr(row, self.rule.qty_field, None) if self.rule.qty_field else None

					self.check_custom_addition_rules()

					if self.uom and self.qty:
						self.add_credit()
			else:
				self.item = getattr(self.doc, self.rule.item_field, None) if self.rule.item_field else None
				self.uom = getattr(self.doc, self.rule.uom_field, None) if self.rule.uom_field else None
				self.qty = getattr(self.doc, self.rule.qty_field, None) if self.rule.qty_field else None

				if self.rule.applicable_for and self.check_application_rule(self.doc):
					return

				self.check_custom_addition_rules()

				if self.uom and self.qty:
					self.add_credit()

	def check_custom_addition_rules(self):
		if self.rule.custom_addition_rules:
			uom = self.uom
			qty = self.qty
			self.uom = self.qty = None

			for rule in self.rule.addition_booking_credit_rules:
				if rule.source_unit_of_measure == uom:
					self.uom = rule.target_unit_of_measure
					self.qty = flt(rule.target_quantity) * flt(qty)
					break

	def apply_standard_rules(self):
		default_uom = frappe.db.get_single_value("Venue Settings", "minute_uom")
		balance = get_balance(self.customer, getdate(self.datetime))
		customer_balance = {x: balance[x] for x in balance if x in self.get_allowed_conversions()}
		customer_uoms = []
		if customer_balance:
			customer_uoms = self.get_ordered_uoms(list(chain.from_iterable(customer_balance.values())))

		if not self.rule.fifo_deduction and self.start.date() == self.end.date():
			for uom in customer_uoms:
				booking_calendar = get_item_calendar(self.item, uom)
				if booking_calendar:
					daily_slots = [
						x
						for x in booking_calendar.get("calendar")
						if x.day == calendar.day_name[self.start.date().weekday()]
					]
					self.min_time = min([x.start_time for x in daily_slots])

					for slot in daily_slots:
						if self.start.time() >= get_time(slot.start_time) and self.end.time() <= get_time(
							slot.end_time
						):
							self.uom = uom
							self.qty = self.duration / (get_uom_in_minutes(self.uom) or 1.0)
							break

				if self.uom and self.qty:
					break

		customer_uom = customer_uoms[0] if customer_uoms else None
		self.uom = self.uom or customer_uom or default_uom
		self.qty = self.qty or self.duration / (get_uom_in_minutes(customer_uom or default_uom) or 1.0)
		self.item = self.get_converted_item(customer_balance, self.uom)

		if self.rule.round_up or self.rule.round_down:
			func = math.ceil if self.rule.round_up else math.floor
			self.qty = func(self.qty)

		if (
			not frappe.db.exists(
				"Booking Credit Usage Reference",
				{"reference_doctype": self.doc.doctype, "reference_document": self.doc.name},
			)
			and self.deduction_is_not_already_registered()
		):
			return self.deduct_credit()

	def apply_custom_rules(self):
		booking_calendar = None
		if self.days > 1:
			calendar_uom = frappe.db.get_single_value("Venue Settings", "minute_uom")
			booking_calendar = get_item_calendar(self.item, calendar_uom)
			if booking_calendar:
				for d in range(self.days):
					daily_slots = [
						x
						for x in booking_calendar.get("calendar")
						if x.day == calendar.day_name[add_days(self.start.date(), d).weekday()]
					]
					min_time = min([x.start_time for x in daily_slots])
					max_time = max([x.end_time for x in daily_slots])
					time_diff = (
						datetime.combine(date.today(), get_time(max_time))
						- datetime.combine(date.today(), get_time(min_time))
					).total_seconds()
					total_duration = time_diff / 60
					self.calculate_intervals(total_duration)

		if not booking_calendar:
			total_duration = self.duration
			self.calculate_intervals(total_duration)

	def calculate_intervals(self, total_duration):
		import numpy as np

		intervals = [
			(x.from_duration, x.to_duration) for x in self.rule.booking_credit_rules if x.duration_interval
		]
		intervals.sort(key=lambda t: t[0])

		levels = [x for x in self.rule.booking_credit_rules if not x.duration_interval]
		min_level = min([x.duration for x in self.rule.booking_credit_rules if not x.duration_interval])

		corresponding_interval = None
		for index, interval in enumerate(intervals):
			if total_duration < interval[0]:
				corresponding_interval = (index - 1) if (index - 1) >= 0 else None
				break

			elif total_duration in range(interval[0], interval[1] + 1) or total_duration > interval[1]:
				corresponding_interval = index

		result = []
		if corresponding_interval is not None:
			selected_rule = [
				x
				for x in self.rule.booking_credit_rules
				if x.from_duration == intervals[corresponding_interval][0]
				and x.to_duration == intervals[corresponding_interval][1]
			][0]
			total_duration -= min(flt(total_duration), flt(selected_rule.to_duration))
			result.append((selected_rule.credit_qty, selected_rule.credit_uom))

		while total_duration > 0:
			if self.rule.round_down and total_duration < min_level:
				break

			closest_index = np.argmin(np.abs(np.array([x.duration for x in levels]) - total_duration))
			total_duration -= min(flt(levels[closest_index].duration), flt(total_duration))
			result.append((levels[closest_index].credit_qty, levels[closest_index].credit_uom))

		for index, res in enumerate(result):
			self.qty = res[0]
			self.uom = res[1]

			self.deduct_credit()

	def add_credit(self):
		doc = frappe.get_doc(
			{
				"doctype": "Booking Credit",
				"date": getdate(self.datetime),
				"customer": self.customer,
				"quantity": self.qty,
				"uom": self.uom,
				"expiration_date": self.expiration_date,
				"item": self.item,
			}
		).insert(ignore_permissions=True)
		return doc.submit()

	def deduct_credit(self):
		if self.rule.valid_from and getdate(self.datetime) >= getdate(self.rule.valid_from):
			usage = frappe.get_doc(
				{
					"doctype": "Booking Credit Usage",
					"datetime": self.datetime,
					"customer": self.customer,
					"quantity": self.qty,
					"uom": self.uom,
					"user": self.user,
					"item": self.item,
				}
			).insert(ignore_permissions=True)

			self.insert_deduction_reference(usage.name)

			return usage.submit()

	def insert_deduction_reference(self, usage):
		frappe.get_doc(
			{
				"doctype": "Booking Credit Usage Reference",
				"booking_credit_usage": usage,
				"reference_doctype": self.doc.doctype,
				"reference_document": self.doc.name,
			}
		).insert(ignore_permissions=True)

	def deduction_is_not_already_registered(self):
		if self.uom == frappe.db.get_single_value("Venue Settings", "month_uom"):
			start_time = get_first_day(getdate(self.start))
			end_time = get_last_day(getdate(self.end))
		else:
			uom_minutes = get_uom_in_minutes(self.uom)
			start_time = min(
				add_to_date(get_datetime(self.end), minutes=(uom_minutes * -1)), get_datetime(self.start)
			)
			if (
				self.min_time
				and get_time(self.min_time)
				>= add_to_date(get_datetime(self.start), minutes=(uom_minutes * -1)).time()
			):
				start_time = get_datetime(self.start).replace(
					hour=get_time(self.min_time).hour, minute=get_time(self.min_time).minute
				)

			end_time = add_to_date(start_time, minutes=(uom_minutes))

		usages = frappe.db.sql(
			f"""SELECT name FROM `tabBooking Credit Usage`
			WHERE datetime > '{start_time}'
			AND datetime < '{end_time}'
			AND coalesce(customer, "") = {frappe.db.escape(self.customer)}
			AND coalesce(user, "") = {frappe.db.escape(self.user)}
		"""
		)

		for usage in usages:
			self.insert_deduction_reference(usage[0])

		if usages:
			return False

		return True

	def get_ordered_uoms(self, balance):
		if self.rule.fifo_deduction:
			return [x["uom"] for x in sorted(balance, key=lambda i: i["date"])]
		else:
			uoms = [x["uom"] for x in balance]
			return frappe.get_all(
				"UOM Conversion Factor",
				filters={
					"from_uom": ("in", uoms),
					"to_uom": frappe.db.get_single_value("Venue Settings", "minute_uom"),
				},
				fields=["from_uom"],
				order_by="value ASC",
				pluck="from_uom",
			)

	def get_expiration_date(self):
		if self.rule.expiration_rule == "End of the month":
			return get_last_day(self.datetime)

		if self.rule.expiration_rule == "End of the year":
			return get_year_ending(self.datetime)

		if not self.rule.expiration_delay:
			return None

		years = self.rule.expiration_delay if self.rule.expiration_rule == "Add X years" else 0
		months = self.rule.expiration_delay if self.rule.expiration_rule == "Add X months" else 0
		days = self.rule.expiration_delay if self.rule.expiration_rule == "Add X days" else 0
		return add_to_date(self.datetime, years=years, months=months, days=days)

	def get_posting_date(self):
		posting_datetime = (
			getattr(self.doc, self.rule.date_field, None) if self.rule.date_field else now_datetime()
		)

		if self.rule.posting_date_rule == "Next first day of the week":
			dt = get_first_day_of_week(posting_datetime)
			if dt == getdate(posting_datetime):
				return dt
			else:
				return dt + timedelta(days=7)

		if self.rule.posting_date_rule == "Next first day of the month":
			if get_first_day(posting_datetime) == getdate(posting_datetime):
				return posting_datetime
			else:
				return get_first_day(posting_datetime, d_months=1)

		if not self.rule.posting_date_delay:
			return posting_datetime

		years = self.rule.posting_date_delay if self.rule.posting_date_rule == "Add X years" else 0
		months = self.rule.posting_date_delay if self.rule.posting_date_rule == "Add X months" else 0
		days = self.rule.posting_date_delay if self.rule.posting_date_rule == "Add X days" else 0

		return add_to_date(posting_datetime, years=years, months=months, days=days)

	def get_allowed_conversions(self):
		return frappe.get_all(
			"Booking Credit Conversions",
			filters={"convertible_item": self.item},
			pluck="booking_credits_item",
		)

	def get_converted_item(self, balance, uom):
		if uom:
			enriched_balance = [
				dict(balance[x][0], **dict(item=x)) for x in balance if balance[x][0].get("uom") == uom
			]
			if enriched_balance:
				items_list = [x["item"] for x in sorted(enriched_balance, key=lambda i: i["date"])]
				if items_list:
					return items_list[0]

		return self.item

	def get_recurrence(self):
		from dateutil import rrule

		if self.rule.recurrence_interval and self.rule.recurrence_end:
			end_date = getattr(self.doc, self.rule.recurrence_end, None) or now_datetime()

			if self.rule.recurrence_interval == "Every Day":
				frequency = rrule.DAILY

			elif self.rule.recurrence_interval == "Every Week":
				frequency = rrule.WEEKLY

			elif self.rule.recurrence_interval == "Every Month":
				frequency = rrule.MONTHLY

			return [
				getdate(x)
				for x in rrule.rrule(
					frequency, dtstart=get_datetime(self.datetime), until=get_datetime(end_date)
				)
			]

		return [self.datetime]
