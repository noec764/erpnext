// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.provide('frappe.dashboards.chart_sources');

frappe.dashboards.chart_sources["Purchase Analytics"] = {
	method: "erpnext.buying.dashboard_chart_source.purchase_analytics.purchase_analytics.get",
	filters: [
		{
			fieldname: "tree_type",
			label: __("Tree Type"),
			fieldtype: "Select",
			options: ["Supplier Group","Supplier","Item Group","Item"],
			default: "Supplier",
			reqd: 1
		},
		{
			fieldname: "doc_type",
			label: __("based_on"),
			fieldtype: "Select",
			options: ["Purchase Order","Purchase Receipt","Purchase Invoice"],
			default: "Purchase Invoice",
			reqd: 1
		},
		{
			fieldname: "value_quantity",
			label: __("Value Or Qty"),
			fieldtype: "Select",
			options: [
				{ "value": "Value", "label": __("Value") },
				{ "value": "Quantity", "label": __("Quantity") },
			],
			default: "Value",
			reqd: 1
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
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
		{
			fieldname: "limit",
			label: __("Max. number of items"),
			fieldtype: "Int"
		},
	]
};
