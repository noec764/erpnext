// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.provide('frappe.dashboards.chart_sources');

frappe.dashboards.chart_sources["Profit And Loss Statement Details"] = {
	method: "erpnext.accounts.dashboard_chart_source.profit_and_loss_statement_details.profit_and_loss_statement_details.get",
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: frappe.defaults.get_user_default("Fiscal Year"),
			reqd: 1
		},
		{
			fieldname: "income_or_expenses",
			label: __("Income or Expenses"),
			fieldtype: "Select",
			options: ["Income", "Expense"],
			reqd: 1
		},
		{
			fieldname: "limit",
			label: __("Number of accounts"),
			fieldtype: "Int"
		}
	]
};
