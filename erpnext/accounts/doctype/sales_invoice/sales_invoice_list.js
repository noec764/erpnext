// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// render
frappe.listview_settings['Sales Invoice'] = {
	add_fields: ["customer", "customer_name", "base_grand_total", "outstanding_amount", "due_date", "company",
		"currency", "is_return"],
	get_indicator: function(doc) {
		const status_colors = {
			"Draft": "gray",
			"Unpaid": "orange",
			"Paid": "green",
			"Return": "darkgray",
			"Credit Note Issued": "darkgray",
			"Unpaid and Discounted": "orange",
			"Partly Paid and Discounted": "yellow",
			"Overdue and Discounted": "red",
			"Overdue": "red",
			"Partly Paid": "yellow",
			"Internal Transfer": "darkgrey"

		};
		return [__(doc.status), status_colors[doc.status], "status,=,"+doc.status];
	},
	right_column: "grand_total",
	onload: function(list_view) {
		frappe.require("assets/erpnext/js/accounting_journal_adjustment.js", () => {
			list_view.page.add_actions_menu_item(
				__("Accounting Journal Adjustment"),
				() => {
					const docnames = list_view.get_checked_items(true);
					new erpnext.journalAdjustment({doctype: list_view.doctype, docnames: docnames})
				},
				true
			);
		});
	}
};
