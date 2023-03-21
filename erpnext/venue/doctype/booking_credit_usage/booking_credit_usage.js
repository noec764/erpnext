// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Booking Credit Usage', {
	setup: function(frm) {
		frm.set_query("user", function() {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: {
					ignore_user_type: 1
				}
			}
		});
	},
	user: function(frm) {
		if (frm.doc.user) {
			frappe.xcall('erpnext.venue.utils.get_customer', {
				user: frm.doc.user
			}).then(r => {
				frm.set_value("customer", r)
			})
		}
	}
});
