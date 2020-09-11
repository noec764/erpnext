// Copyright (c) 2020, Dokos SAS and Contributors
// License: See license.txt

frappe.views.calendar["Event Slot"] = {
	field_map: {
		"start": "starts_on",
		"end": "ends_on",
        "id": "name",
        "title": "event_subject"
    },
    no_all_day: true
};