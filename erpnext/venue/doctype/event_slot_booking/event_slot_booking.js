// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Event Slot Booking', {
	setup(frm) {
		frm.set_query("user", function() {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: {
					ignore_user_type: 1
				}
			}
		});
	},
});
