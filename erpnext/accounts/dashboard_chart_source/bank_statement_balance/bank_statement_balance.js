// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.provide('frappe.dashboards.chart_sources');

frappe.dashboards.chart_sources["Bank Statement Balance"] = {
	method: "erpnext.accounts.dashboard_chart_source.bank_statement_balance.bank_statement_balance.get",
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "bank_account",
			label: __("Bank Account"),
			fieldtype: "Link",
			options: "Bank Account",
		},
		{
			fieldname: "range",
			label: __("Range"),
			fieldtype: "Select",
			options: [
				{ "value": "Weekly", "label": __("Weekly") },
				{ "value": "Monthly", "label": __("Monthly") },
				{ "value": "Quarterly", "label": __("Quarterly") },
				{ "value": "Yearly", "label": __("Yearly") }
			],
			default: "Monthly",
			reqd: 1
		},
	]
};
