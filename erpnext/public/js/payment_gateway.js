// Copyright (c) 2019, Dokos and Contributors
// License: See license.txt

frappe.ui.form.on('Payment Gateway', {
	setup(frm) {
		frm.set_query('fee_account', (doc) => {
			return {
				filters: {
					"is_group": 0,
					"account_type": "Expense Account"
				}
			};
		});

		frm.set_query('tax_account', (doc) => {
			return {
				filters: {
					"is_group": 0,
					"account_type": "Tax"
				}
			};
		});
	}
});