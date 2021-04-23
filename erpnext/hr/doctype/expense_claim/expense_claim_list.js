frappe.listview_settings['Expense Claim'] = {
	add_fields: ["total_claimed_amount", "docstatus", "company"],
	get_indicator: function(doc) {
		if(doc.status == "Paid") {
			return [__("Paid"), "green", "status,=,Paid"];
		}else if(doc.status == "Unpaid") {
			return [__("Unpaid"), "orange", "status,=,Unpaid"];
		} else if(doc.status == "Rejected") {
			return [__("Rejected"), "gray", "status,=,Rejected"];
		}
	},
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
