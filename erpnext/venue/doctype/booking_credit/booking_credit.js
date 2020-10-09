// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt
frappe.ui.form.on('Booking Credit', {
	onload: function(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Booking Credit Ledger"];
	},
	refresh: function(frm) {
		frm.trigger("add_balance");
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
	add_balance(frm) {
		if (!frm.is_new() && frm.doc.customer) {
			frappe.xcall('erpnext.venue.doctype.booking_credit.booking_credit.get_balance', {
				customer: frm.doc.customer,
				date: frm.doc.date
			}).then(r => {
				const credits = r.map(d => { return d.balance });
				const max_count = Math.max.apply(null, credits);
				frm.dashboard.add_section(frappe.render_template('booking_credit_dashboard',
				{
					balance: r,
					customer: frm.doc.customer,
					date: frm.doc.date,
					max_count: max_count
				}), __("Booking Credits Balance"));
				frm.dashboard.show();
			})
		}
	}
});
