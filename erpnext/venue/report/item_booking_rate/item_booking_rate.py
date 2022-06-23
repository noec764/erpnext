# Copyright (c) 2022, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate
from frappe.utils.dateutils import get_dates_from_timegrain

from erpnext.venue.doctype.item_booking.item_booking import get_item_calendar


def execute(filters=None):
	data, chart = get_data(filters)
	columns = get_columns()
	return columns, data, [], chart


def get_data(filters):
	if not filters.get("date_range"):
		return []

	status_filter = (
		"Confirmed, Not Confirmed"
		if filters.get("status") == "Confirmed and not confirmed"
		else "Confirmed"
	)

	item_booking = frappe.get_all(
		"Item Booking",
		filters={
			"starts_on": ("between", filters.get("date_range")),
			"status": ("in", (f"{status_filter}")),
		},
		fields=["status", "name", "item", "item_name", "starts_on", "ends_on"],
	)

	items_dict = defaultdict(lambda: defaultdict(float))

	item_list = list(set(ib.item for ib in item_booking))
	for item in item_list:
		calendar, capacity_per_day, total_capacity = get_calendar_capacity(
			filters.get("company"), filters.get("date_range"), item
		)
		items_dict[item]["calendar"] = calendar.get("calendar")
		items_dict[item]["calendar_name"] = calendar.get("name")
		items_dict[item]["capacity"] = total_capacity

	# Get minutes booked
	for ib in item_booking:
		diff = timedelta(0)
		for date in get_dates_from_timegrain(ib.get("starts_on"), ib.get("ends_on")):
			for line in items_dict[ib["item"]]["calendar"]:
				if line.day == date.strftime("%A"):
					schedule_start = get_datetime(date) + line.start_time
					schedule_end = get_datetime(date) + line.end_time
					booking_start = get_datetime(ib.get("starts_on"))
					booking_end = get_datetime(ib.get("ends_on"))
					if getdate(ib.get("starts_on")) != getdate(date):
						booking_start = schedule_start
					if getdate(ib.get("ends_on")) != getdate(date):
						booking_end = schedule_end

					diff += booking_end - booking_start

		ib["diff_minutes"] = diff.total_seconds() / 60.0

		items_dict[ib["item"]]["item_name"] = ib["item_name"]
		items_dict[ib["item"]]["total"] += flt(ib["diff_minutes"]) / 60.0

	output = sorted(
		[{"item": x, **items_dict[x]} for x in items_dict], key=lambda x: x["item"].lower()
	)

	for line in output:
		line["percent"] = (
			flt(line["total"]) / flt(line["capacity"]) if line["capacity"] else 1.0
		) * 100.0

	chart_data = get_chart_data(output)

	return output, chart_data


def get_calendar_capacity(company, date_range, item):
	holiday_list = frappe.get_cached_value("Company", company, "default_holiday_list")
	holidays = frappe.get_all(
		"Holiday",
		filters={
			"parent": holiday_list,
			"holiday_date": ("between", date_range),
		},
		pluck="holiday_date",
	)

	calendar = get_item_calendar(item)

	for line in calendar.get("calendar"):
		line["capacity"] = (line.get("end_time") - line.get("start_time")).total_seconds() / 3600

	capacity_per_day = {}
	total_capacity = 0.0

	for date in get_dates_from_timegrain(date_range[0], date_range[1]):
		if date not in holidays:
			capacity_per_day[date] = sum(
				flt(x.capacity) for x in calendar.get("calendar") if x["day"] == date.strftime("%A")
			)
			total_capacity += capacity_per_day[date]
		else:
			capacity_per_day[date] = 0.0

	return calendar, capacity_per_day, total_capacity


def get_columns():
	columns = [
		{"label": _("Item"), "fieldtype": "Link", "fieldname": "item", "options": "Item", "width": 180},
		{"label": _("Item Name"), "fieldtype": "Data", "fieldname": "item_name", "width": 300},
		{
			"label": _("Reference Calendar"),
			"fieldtype": "Link",
			"fieldname": "calendar_name",
			"options": "Item Booking Calendar",
			"width": 250,
		},
		{
			"label": _("Bookable Hours"),
			"fieldtype": "Float",
			"fieldname": "capacity",
			"width": 200,
		},
		{
			"label": _("Hours Booked"),
			"fieldtype": "Float",
			"fieldname": "total",
			"width": 250,
		},
		{
			"label": _("Booking rate"),
			"fieldtype": "Percent",
			"fieldname": "percent",
			"width": 250,
		},
	]

	return columns


def get_chart_data(data):
	return {
		"data": {
			"labels": [x.get("item_name") for x in data],
			"datasets": [
				{"name": _("Capacity (Hours)"), "values": [round(x.get("capacity"), 2) for x in data]},
				{"name": _("Bookings (Hours)"), "values": [round(x.get("total"), 2) for x in data]},
			],
		},
		"type": "bar",
		"colors": ["#bae6cf", "green"],
	}
