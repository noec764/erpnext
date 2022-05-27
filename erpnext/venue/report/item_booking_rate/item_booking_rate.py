# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt
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

	# Get minutes booked
	for ib in item_booking:
		ib["diff_minutes"] = (ib.get("ends_on") - ib.get("starts_on")).total_seconds() / 60.0

		items_dict[ib["item"]]["item_name"] = ib["item_name"]
		items_dict[ib["item"]]["total"] += flt(ib["diff_minutes"]) / 60.0
		items_dict[ib["item"]]["capacity"] = 0.0

	get_calendar_capacity(filters, items_dict)

	output = [{"item": x, **items_dict[x]} for x in items_dict]

	for line in output:
		line["percent"] = (
			flt(line["total"]) / flt(line["capacity"]) if line["capacity"] else 1.0
		) * 100.0

	chart_data = get_chart_data(output)

	return output, chart_data


def get_calendar_capacity(filters, items):
	holiday_list = frappe.get_cached_value("Company", filters.get("company"), "default_holiday_list")
	holidays = frappe.get_all(
		"Holiday",
		filters={
			"parent": holiday_list,
			"holiday_date": ("between", [filters.get("date_range")[0], filters.get("date_range")[1]]),
		},
		pluck="holiday_date",
	)

	for item in items:
		daily_capacity = defaultdict(float)
		calendar = get_item_calendar(item)

		for line in calendar.get("calendar"):
			daily_capacity[line.day] += (
				line.get("end_time") - line.get("start_time")
			).total_seconds() / 3600

		for index, date in enumerate(filters.get("date_range")):
			for sub_date in get_dates_from_timegrain(
				filters.get("date_range")[index - 1] if index > 0 else filters.get("date_range")[0], date
			):
				if sub_date not in holidays:
					items[item]["capacity"] += flt(daily_capacity.get(sub_date.strftime("%A")))


def get_columns():
	columns = [
		{"label": _("Item"), "fieldtype": "Link", "fieldname": "item", "options": "Item", "width": 180},
		{"label": _("Item Name"), "fieldtype": "Data", "fieldname": "item_name", "width": 250},
		{
			"label": _("Hours Booked"),
			"fieldtype": "Int",
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
	}
