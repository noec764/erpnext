// Copyright (c) 2022, Dokos SAS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Cash Flow Budget"] = {
	"collapse_all_rows": 1,
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname": "bank_account",
			"label": __("Bank Account"),
			"fieldtype": "Link",
			"options": "Bank Account",
			"default": frappe.boot.sysdefaults.default_bank_account_name,
			"get_query": function () {
				var company = frappe.query_report.get_filter_value('company')
				return {
					filters: {
						company: company
					}
				}
			},
			"reqd": 1
		},
		{
			"fieldname": "period_end_date",
			"label": __("End Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.add_months(frappe.datetime.month_start(), 6), -1),
			"reqd": 1,
			"min_date": frappe.datetime.now_date(true)
		},
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column && column.fieldname == "label") {
			value = $(`<span>${value}</span>`);

			var $value = $(value).css("font-weight", "bold");

			value = $value.wrap("<p></p>").parent().html();
		}

		return value;
	}
};
