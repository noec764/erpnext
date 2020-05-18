// Copyright (c) 2019, Dokos SAS and Contributors
// For license information, please see license.txt

frappe.ui.form.on('Accounting Journal', {
	setup: function(frm) {
		frm.set_query("account", function() {
			return {
				filters: {
					'account_type': ('in', ('Bank', 'Cash')),
					'company': frm.doc.company,
					'is_group': 0
				}
			};
		});
	}
});
