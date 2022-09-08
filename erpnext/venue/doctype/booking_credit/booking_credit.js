// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt
frappe.ui.form.on('Booking Credit', {
	setup: function(frm) {
		frm.get_balance = false;
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
	refresh: function(frm) {
		frm.trigger("add_balance");
	},
	user: function(frm) {
		if (frm.doc.user) {
			frappe.xcall('erpnext.venue.utils.get_customer', {
				user: frm.doc.user
			}).then(r => {
				frm.set_value("customer", r)
			})
		}
	},
	add_balance(frm) {
		if (!frm.is_new() && frm.doc.customer && !frm.get_balance) {
			frm.get_balance = true;
			frappe.xcall('erpnext.venue.doctype.booking_credit.booking_credit.get_balance', {
				customer: frm.doc.customer,
				date: frm.doc.date
			}).then(r => {
				const credits = Object.keys(r).map(m => {
					return r[m]
				}).flat().map(d => {
					return d.balance
				});
				const max_count = Math.max.apply(null, credits) > 0 ? Math.max.apply(null, credits) : Math.min.apply(null, credits);

				frm.dashboard.add_section(frappe.render_template('booking_credit_dashboard',
				{
					balance: Object.keys(r).map(f => {
						return flatten_credits(r, f)
					}).flat(),
					customer: frm.doc.customer,
					date: frm.doc.date,
					max_count: max_count,
				}), __("Booking Credits Balance"));
				frm.dashboard.show();
				frm.get_balance = false;

				frm.trigger('bind_reconciliation_btns');
			})
		}
	},

	bind_reconciliation_btns(frm) {
		$(frm.dashboard.wrapper).find('.uom-reconciliation-btn').on("click", e => {
			frappe.xcall("erpnext.venue.page.booking_credits.booking_credits.reconcile_credits", {
				customer: $(e.target).attr("data-customer"),
				target_uom: $(e.target).attr("data-uom"),
				target_item: $(e.target).attr("data-target-item"),
				source_item: $(e.target).attr("data-source-item"),
				date: frm.doc.date
			}).then(r => {
				frappe.show_alert(r)
				frm.refresh()
			})
		})
	}
});

function flatten_credits(obj, item) {
	return obj[item].map(f => {
		return {...f, item: item}
	})
}
