// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Bank Reconciliation Statement"] = {
	"filters": [
		{
			"fieldname":"bank_account",
			"label": __("Bank Account"),
			"fieldtype": "Link",
			"options": "Bank Account",
			"default": frappe.boot.sysdefaults.default_bank_account_name,
			"reqd": 1
		},
		{
			"fieldname":"report_date",
			"label": __("Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		}
	],
	onload: (report) => {
		report.page.add_action_item(__("Go to Bank Reconciliation Dashboard"), function() {
			frappe.set_route("bank-reconciliation", {bank_account: report.filters.filter(f => f.fieldname == "bank_account")[0].value})
		});
	}
}