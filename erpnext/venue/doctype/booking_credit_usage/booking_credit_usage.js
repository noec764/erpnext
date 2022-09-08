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

		frm.set_query("item", function() {
			return {
				query: "erpnext.venue.doctype.booking_credit_conversion.booking_credit_conversion.get_convertible_items",
			};
		});

		frm.set_query("uom", function() {
			return {
				query: "erpnext.controllers.queries.get_uoms",
				filters: {
					"item_code": frm.doc.item
				}
			};
		});
	},
	onload: function(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Booking Credit Ledger"];
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
