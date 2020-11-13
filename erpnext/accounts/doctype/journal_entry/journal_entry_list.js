frappe.listview_settings['Journal Entry'] = {
	add_fields: ["voucher_type", "posting_date", "total_debit", "company", "user_remark"],
	get_indicator: function(doc) {
		if(doc.docstatus==0) {
			return [__("Draft", "red", "docstatus,=,0")]
		} else if(doc.docstatus==2) {
			return [__("Cancelled", "gray", "docstatus,=,2")]
		} else {
			return [__(doc.voucher_type), "blue", "voucher_type,=," + doc.voucher_type]
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
