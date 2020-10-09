// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Booking Credit Usage', {
	onload: function(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Booking Credit Ledger"];
	},
	user: function(frm) {
		if (frm.doc.user) {
			frappe.xcall('erpnext.venue.doctype.booking_credit.booking_credit.get_customer', {
				user: frm.doc.user
			}).then(r => {
				frm.set_value("customer", r)
			})
		}
	},
});
