// Copyright (c) 2019, Dokos SAS and Contributors
// License: See license.txt

frappe.views.calendar["Item Booking"] = {
	field_map: {
		"start": "starts_on",
		"end": "ends_on",
		"id": "name",
		"title": "title",
		"allDay": "all_day",
		"rrule": "rrule",
		"color": "color",
		"status": "status",
		"doctype": "doctype"
	},
	status_color: {
		"In cart": "orange",
		"Not confirmed": "darkgray",
		"Confirmed": "green",
		"Cancelled": "red"
	},
	filters: [["Item Booking", "status", "!=", "Cancelled"]],
	get_events_method: "erpnext.venue.doctype.item_booking.item_booking.get_events_for_calendar"
};