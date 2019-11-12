// Copyright (c) 2019, Dokos SAS and Contributors
// License: See license.txt

frappe.views.calendar["Item Booking"] = {
	field_map: {
		"start": "starts_on",
		"end": "ends_on",
		"id": "name",
		"title": "title",
		"allDay": "allDay"
	},
	filters: [
		{
			"fieldtype": "Link",
			"fieldname": "item",
			"options": "Item",
			"label": __("Item")
		}
	],
	get_events_method: "erpnext.stock.doctype.item_booking.item_booking.get_events"
};