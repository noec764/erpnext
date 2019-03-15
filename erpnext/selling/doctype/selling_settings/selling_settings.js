// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Selling Settings', {
	setup: function(frm) {
		frm.set_query('customer_group', {'is_group': 0});
		frm.set_query('territory', {'is_group': 0});
	}
});
