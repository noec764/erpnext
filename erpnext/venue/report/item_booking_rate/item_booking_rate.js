// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Item Booking Rate"] = {
	filters: [
		{
			fieldtype: 'Link',
			label: __('Company'),
			fieldname: 'company',
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
		},
		{
			fieldtype: 'DateRange',
			label: __('Date Range'),
			fieldname: 'date_range',
			default: [frappe.datetime.add_months(frappe.datetime.get_today(),-1), frappe.datetime.get_today()],
			reqd: 1
		},
		{
			fieldtype: 'Select',
			label: __('Status'),
			fieldname: 'status',
			default: "Confirmed",
			options: [
				{
					"value": "Confirmed",
					"label": __("Confirmed")
				},
				{
					"value": "Confirmed and not confirmed",
					"label": __("Confirmed and not confirmed")
				}
			],
			reqd: 1
		}
	]
};
