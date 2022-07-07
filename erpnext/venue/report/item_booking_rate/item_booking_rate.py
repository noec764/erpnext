# Copyright (c) 2022, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict
from datetime import timedelta

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt, format_date, get_datetime, getdate
from frappe.utils.dateutils import get_dates_from_timegrain

from erpnext.venue.doctype.item_booking.item_booking import get_item_calendar


def execute(filters=None):
	data, chart = get_data(filters)
	columns = get_columns(filters)
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

	items_dict = defaultdict(dict)

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
		if "item_name" not in items_dict[ib["item"]]:
			items_dict[ib["item"]]["item_name"] = ib["item_name"]

		if "total" not in items_dict[ib["item"]]:
			items_dict[ib["item"]]["total"] = 0.0

		if "bookings" not in items_dict[ib["item"]]:
			items_dict[ib["item"]]["bookings"] = []

		if "free_hours" not in items_dict[ib["item"]]:
			items_dict[ib["item"]]["free_hours"] = 0.0

		if "billed_hours" not in items_dict[ib["item"]]:
			items_dict[ib["item"]]["billed_hours"] = 0.0

		if "average_price" not in items_dict[ib["item"]]:
			items_dict[ib["item"]]["average_price"] = 0.0

		if filters.show_billing:
			ib["total_price"] = get_item_booking_price(ib.name)

		diff = timedelta(0)
		capacity = 0.0
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
					capacity += line.get("capacity")

		ib["total"] = flt(diff.total_seconds() / 3600.0)
		ib["capacity"] = capacity
		if filters.show_billing:
			ib["average_price"] = ib["total_price"] / ib["total"]
			ib["free_hours"] = ib["total"] if ib["total_price"] == 0 else 0.0
			ib["billed_hours"] = ib["total"] if ib["total_price"] > 0 else 0.0

		items_dict[ib["item"]]["total"] += ib["total"]
		items_dict[ib["item"]]["bookings"].append(ib)
		if filters.show_billing:
			items_dict[ib["item"]]["free_hours"] += ib["free_hours"]
			items_dict[ib["item"]]["billed_hours"] += ib["billed_hours"]

	if filters.show_billing:
		for item in items_dict:
			items_dict[item]["average_price"] = (
				sum(x["total_price"] for x in items_dict[item]["bookings"]) / items_dict[item]["total"]
			)

	sorted_list = sorted(
		[{"item": f"{x}: {items_dict[x]['item_name']}", **items_dict[x]} for x in items_dict],
		key=lambda x: x["item"].lower(),
	)

	if filters.show_bookings:
		output = []
		for row in sorted_list:
			output.append(row)
			for booking in row.get("bookings"):
				booking.item = None
				booking.item_name = None
				booking["item_booking"] = booking.name
				booking["booking_dates"] = (
					f"{format_date(booking.starts_on)} - {format_date(booking.ends_on)}"
					if getdate(booking.starts_on) != getdate(booking.ends_on)
					else format_date(booking.starts_on)
				)
				output.append(booking)

	else:
		output = sorted_list

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


def get_item_booking_price(item_booking):
	sales_order_item, sales_order = frappe.qb.DocType("Sales Order Item"), frappe.qb.DocType(
		"Sales Order"
	)
	amounts = (
		frappe.qb.from_(sales_order_item)
		.from_(sales_order)
		.select(Sum(sales_order_item.amount))
		.where(
			(sales_order_item.item_booking == item_booking)
			& (sales_order.name == sales_order_item.parent)
			& (sales_order.docstatus == 1)
			& (sales_order.per_billed == 100.0)
		)
	).run()

	return flt(amounts[0][0])


def get_columns(filters):
	columns = [
		{"label": _("Item"), "fieldtype": "Data", "fieldname": "item", "width": 300},
		{
			"label": _("Reference Calendar"),
			"fieldtype": "Link",
			"fieldname": "calendar_name",
			"options": "Item Booking Calendar",
			"width": 250,
		},
	]

	if filters.show_bookings:
		columns.extend(
			[
				{
					"label": _("Item Booking"),
					"fieldtype": "Link",
					"fieldname": "item_booking",
					"options": "Item Booking",
					"width": 200,
				},
				{
					"label": _("Dates"),
					"fieldtype": "Data",
					"fieldname": "booking_dates",
					"width": 200,
				},
			]
		)

	columns.extend(
		[
			{
				"label": _("Bookable Hours"),
				"fieldtype": "Float",
				"fieldname": "capacity",
				"width": 180,
			}
		]
	)

	if filters.show_billing:
		columns.extend(
			[
				{
					"label": _("Free Hours"),
					"fieldtype": "Float",
					"fieldname": "free_hours",
					"width": 180,
				},
				{
					"label": _("Billed Hours"),
					"fieldtype": "Float",
					"fieldname": "billed_hours",
					"width": 180,
				},
				{
					"label": _("Average Price / Hour"),
					"fieldtype": "Currency",
					"fieldname": "average_price",
					"width": 180,
				},
			]
		)

	columns.extend(
		[
			{
				"label": _("Hours Booked"),
				"fieldtype": "Float",
				"fieldname": "total",
				"width": 180,
			},
			{
				"label": _("Booking rate"),
				"fieldtype": "Percent",
				"fieldname": "percent",
				"width": 180,
				"bold": 1,
			},
		]
	)

	return columns


def get_chart_data(data):
	return {
		"data": {
			"labels": [x.get("item_name") for x in data if not x.get("item_booking")],
			"datasets": [
				{
					"name": _("Capacity (Hours)"),
					"values": [round(x.get("capacity"), 2) for x in data if not x.get("item_booking")],
				},
				{
					"name": _("Bookings (Hours)"),
					"values": [round(x.get("total"), 2) for x in data if not x.get("item_booking")],
				},
			],
		},
		"type": "bar",
		"colors": ["#bae6cf", "green"],
	}
