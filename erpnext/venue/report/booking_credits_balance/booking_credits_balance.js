// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Booking Credits Balance"] = {
	"filters": [
		{
			"fieldname": "customer",
			"fieldtype": "Link",
			"label": __("Customer"),
			"options": "Customer"
		},
		{
			"fieldname": "customer_group",
			"fieldtype": "Link",
			"label": __("Customer Group"),
			"options": "Customer Group"
		},
		{
			"fieldname": "booking_credit_type",
			"fieldtype": "Link",
			"label": __("Booking Credit Type"),
			"options": "Booking Credit Type"
		}
	]
};
