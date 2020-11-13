// Copyright (c) 2020, Dokos and Contributors
// License: See license.txt

erpnext.journalAdjustment = class AccountingJournalAdjustment {
	constructor(opts) {
		Object.assign(this, opts);
		this.make()
	}

	make() {
		const dialog = new frappe.ui.Dialog({
			title: __('Adjust the accounting journal'),
			fields: [
				{
					"label" : "Current Journal",
					"fieldname": "current_journal",
					"fieldtype": "HTML"
				}
			],
			primary_action: function() {
				console.log("Hello")
			},
			primary_action_label: __('Submit')
		})
	}
}