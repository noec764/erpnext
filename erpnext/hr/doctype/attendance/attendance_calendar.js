// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
frappe.views.calendar["Attendance"] = {
	options: {
		headerToolbar: {
			left: 'prev,next today',
			center: 'title',
			right: 'month'
		},
		displayEventTime: false
	},
	field_map: {
		"id": "name",
		"start": "start",
		"end": "end",
		"allDay": "all_day",
		"status": "status",
		"color": "color",
		"secondary_status": "status",
	},
	secondary_status_color: {
		"Present": "green",
		"Work From Home": "red",
		"Absent": "red",
		"On Leave": "red",
		"Half Day": "orange"
	},
	get_events_method: "erpnext.hr.doctype.attendance.attendance.get_events"
};
