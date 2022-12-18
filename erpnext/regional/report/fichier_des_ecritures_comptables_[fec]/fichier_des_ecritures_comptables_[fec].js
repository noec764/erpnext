// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Fichier des Ecritures Comptables [FEC]"] = {
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
			"fieldname": "fiscal_year",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": frappe.defaults.get_user_default("fiscal_year"),
			"reqd": 1
		}
	],
	onload: function(query_report) {
		query_report.page.add_inner_button(__("Export"), function() {
			fec_export(query_report);
		});

		query_report.page.add_inner_button(__("Export with reference files"), function() {
			fec_export(query_report, true);
		});

		query_report.add_chart_buttons_to_toolbar = function() {
			//
		};

		query_report.add_card_button_to_toolbar = function() {
			//
		};

		query_report.export_report = function() {
			fec_export(query_report);
		};
	}
};

const fec_export = function(query_report, with_files=false) {
	frappe.show_alert({
		message: __("Your FEC is being prepared"),
		indicator: "green",
	})

	open_url_post(frappe.request.url, {
		cmd: "erpnext.regional.report.fichier_des_ecritures_comptables_[fec].fichier_des_ecritures_comptables_[fec].export_report",
		filters: {
			fiscal_year: query_report.get_values().fiscal_year,
			company:query_report.get_values().company,
		},
		with_files: with_files
	})
};