// Copyright (c) 2021, Dokos SAS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Cadrage TVA base par taux"] = {
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value || "", row, column, data);
		if (data && data.bold) {
			value = value.bold();
		}

		if (data && data.warn_if_negative && column.colIndex > 2 && data[column.fieldname] != 0) {
			var $value = $(value).css("font-weight", "bold").addClass("text-danger");
			value = $value.wrap("<p></p>").parent().html();
		}
		return value;
	},
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname":"regime",
			"label": __("Regim"),
			"fieldtype": "Select",
			"options": "VAT on amounts received",
			"default": "VAT on amounts received",
			"reqd": 1
		},
		{
			"fieldname":"fiscal_year",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options":'Fiscal Year',
			"default": frappe.sys_defaults.fiscal_year,
			"reqd": 1,
			on_change: () => {
				set_date()
			}
		},
		{
			"fieldname":"date",
			"label": __("Date"),
			"fieldtype": "Date",
			"reqd": 1
		}
	],
	onload: function(report) {
		set_date()
	},
	after_datatable_render: (dt) => {
		dt.style.setStyle(`.dt-cell--col-3:not(.dt-cell--header):not(.dt-cell--filter)`, {
			backgroundColor: "#f5f7fa"
		})

		dt.style.setStyle(`[data-row-index="${dt.datamanager.data.length - 1}"]`, {
			backgroundColor: "#f5f7fa"
		})
	}
};

const set_date = () => {
	const fiscal_year = frappe.query_report.get_filter_value('fiscal_year')
	frappe.model.with_doc("Fiscal Year", fiscal_year, function(r) {
		const fy = frappe.model.get_doc("Fiscal Year", fiscal_year);
		frappe.query_report.set_filter_value({
			date: fy.year_end_date >= frappe.datetime.nowdate() ? frappe.datetime.nowdate() : fy.year_end_date
		});
	});
}