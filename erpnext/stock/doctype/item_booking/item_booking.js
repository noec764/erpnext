// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Booking', {
	setup(frm) {
		frappe.realtime.on('event_synced', (data) => {
			frappe.show_alert({message: data, indicator: 'green'});
		})
	},
	refresh(frm) {
		if (frm.doc.docstatus == 1) {
			frm.page.add_action_item(__("Create a quotation"), () => {
				frappe.xcall(
					"erpnext.stock.doctype.item_booking.item_booking.make_quotation",
					{ source_name: frm.doc.name }
				).then(r => {
					if (r) {
						frappe.set_route('Form', r.doctype, r.name);
					}
				})
			})
		}

		frm.set_query('party_type', () => {
			return {
				filters: {
					name: ['in', ['Lead', 'Customer']]
				}
			};
		});

		frm.set_query('sales_uom', () => {
			return {
				query:"erpnext.accounts.doctype.pricing_rule.pricing_rule.get_item_uoms",
				filters: {'value': frm.doc.item, apply_on: 'Item Code'}
			}
		})

		frm.set_query("user", function() {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: {
					ignore_user_type: 1
				}
			}
		});

		if (frm.delayInfo) {
			clearInterval(frm.delayInfo)
		}

		if (frm.doc.docstatus === 0) {
			frappe.db.get_single_value("Stock settings", "clear_item_booking_draft_duration")
				.then(r => {
					if (r && r>0) {
						frm.delayInfo = setInterval( () => {
							const delay = frappe.datetime.get_minute_diff(
								frappe.datetime.add_minutes(frm.doc.modified, r),
								frappe.datetime.now_datetime())
							frm.set_intro()
							if (delay > 0) {
								frm.set_intro(__("This document will be automatically deleted in {0} minutes if not validated.", [delay]))
							}
						}, 10000 )
					}
				} )
		}
	},
	sync_with_google_calendar(frm) {
		frm.trigger('get_google_calendar');
	},
	item(frm) {
		frm.trigger('get_google_calendar');
	},
	get_google_calendar(frm) {
		if (frm.doc.sync_with_google_calendar && frm.doc.item && !frm.doc.google_calendar) {
			frappe.db.get_value("Item", frm.doc.item, "google_calendar", r => {
				r&&frm.set_value("google_calendar", r.google_calendar);
			})
		}
	},
	repeat_this_event: function(frm) {
		if(frm.doc.repeat_this_event === 1) {
			new frappe.CalendarRecurrence(frm);
		}
	}
});
