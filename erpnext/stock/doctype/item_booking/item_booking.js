// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Booking', {
	setup(frm) {
		frappe.realtime.on('event_synced', (data) => {
			frappe.show_alert({message: data.message, indicator: 'green'});
			frm.reload_doc();
		})
	},
	refresh(frm) {
		frm.page.clear_actions_menu();
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

		frm.trigger('add_to_quotation');
		frm.trigger('add_to_sales_order');

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

		frm.set_query('google_calendar', function() {
			return {
				filters: {
					"reference_document": "Item Booking"
				}
			};
		});

		if (frm.delayInfo) {
			clearInterval(frm.delayInfo)
		}

		if (!frm.is_new() && frm.doc.status === "In Cart") {
			frappe.db.get_single_value("Stock settings", "clear_item_booking_draft_duration")
				.then(r => {
					frm.delayInfo && clearInterval(frm.delayInfo);

					if (r && r>0 && !frm.delayInfo) {
						frm.delayInfo = setInterval( () => {
							const delay = frappe.datetime.get_minute_diff(
								frappe.datetime.add_minutes(frm.doc.modified || frappe.datetime.now_datetime(), r),
								frappe.datetime.now_datetime())
							frm.set_intro()
							if (delay > 0) {
								frm.set_intro(__("This document will be automatically deleted in {0} minutes if not validated.", [delay]))
							}
						}, 10000 )
					}
				} )
		}

		frm.trigger('add_repeat_text')
	},
	add_repeat_text(frm) {
		if (frm.doc.rrule) {
			new frappe.CalendarRecurrence(frm, false);
		}
	},
	sync_with_google_calendar(frm) {
		frm.trigger('get_google_calendar_and_color');
	},
	item(frm) {
		frm.trigger('get_google_calendar_and_color');
	},
	get_google_calendar_and_color(frm) {
		if (frm.doc.item) {
			frappe.db.get_value("Item", frm.doc.item, ["google_calendar", "calendar_color"], r => {
				if (r) {
					r.google_calendar&&frm.set_value("google_calendar", r.google_calendar);
					r.calendar_color&&frm.set_value("color", r.calendar_color);
				}
			})
		}
	},
	repeat_this_event(frm) {
		if(frm.doc.repeat_this_event === 1) {
			new frappe.CalendarRecurrence(frm, true);
		}
	},
	add_to_quotation(frm){
		frm.page.add_action_item(__("Add to an existing quotation"), () => {
			add_to_transaction(frm, "Quotation")
		})
	},
	add_to_sales_order(frm){
		frm.page.add_action_item(__("Add to an existing sales order"), () => {
			add_to_transaction(frm, "Sales Order")
		})
	}
});

const add_to_transaction = (frm, transaction_type) => {
	const d = new frappe.ui.form.MultiSelectDialog({
		doctype: transaction_type,
		target: "Item Booking",
		date_field: "transaction_date" || undefined,
		setters: {},
		get_query: () => {
			return {
				filters: {
					docstatus: ("!=", 2)
				}
			}
		},
		action: function(selections, args) {
			const values = selections;
			if(values.length === 0){
				frappe.msgprint(__("Please select {0}", [opts.source_doctype]))
				return;
			}
			d.dialog.hide();
			new ItemSelector({values: values, frm: frm, transaction_type: transaction_type})
		},
	});
}

class ItemSelector {
	constructor(opts) {
		Object.assign(this, opts)
		this.make()
	}

	make() {
		this.get_data()
		.then(r => {
			this.items = r.filter(f => !f.item_booking);
			this.make_dialog();
		})
	}

	get_data() {
		return frappe.xcall("erpnext.stock.doctype.item_booking.item_booking.get_transactions_items", {
			transaction_type: this.transaction_type,
			transactions: this.values
		})
	}

	make_dialog() {
		const me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("Select an item"),
			fields: [{ fieldtype: "HTML", fieldname: "items_area" }],
			primary_action_label: __("Select"),
			primary_action: () => {
				const value = this.get_checked_values()
				if (value.length) {
					frappe.xcall("erpnext.stock.doctype.item_booking.item_booking.update_linked_transaction", {
						transaction_type: this.transaction_type,
						line_item: value[0],
						item_booking: this.frm.doc.name
					}).then(r => {
						if (!r) {
							frappe.show_alert({
								message: __("The quotation has been updated", [__(me.transaction_type).toLowerCase()]),
								indicator: "green"
							})
							this.frm.reload_doc();
						}
					})
				}
				this.dialog.hide();
			}
		});
		this.$parent = $(this.dialog.body);
		this.$wrapper = this.dialog.fields_dict.items_area.$wrapper.append(`<div class="results"
			style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);

		this.$items = this.$wrapper.find('.results');
		this.$items.append(this.make_list_row());
		this.render_result_list();
		this.bind_events();
		this.dialog.show()
	}

	make_list_row(result={}) {
		const me = this;
		const head = Object.keys(result).length === 0;

		let contents = ``;
		let columns = ["parent", "item_code", "qty", "uom"];

		columns.forEach(function(column) {
			contents += `<div class="list-item__content ellipsis">
				${
					head ? `<span class="ellipsis">${__(frappe.model.unscrub(column))}</span>`

					: (column !== "name" ? `<span class="ellipsis">${__(result[column])}</span>`
						: `<a href="${"#Form/"+ me.doctype + "/" + result[column]}" class="list-id ellipsis">
							${__(result[column])}</a>`)
				}
			</div>`;
		})

		let $row = $(`<div class="list-item">
			<div class="list-item__content" style="flex: 0 0 10px;">
				${head ? '' : `<input type="checkbox" class="list-row-check" data-item-name="${result.name}" ${result.checked ? 'checked' : ''}>`}
			</div>
			${contents}
		</div>`);

		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container" data-item-name="${result.name}"></div>`).append($row);
		return $row;
	}

	get_checked_values() {
		// Return name of checked value.
		return this.$items.find('.list-item-container').map(function() {
			if ($(this).find('.list-row-check:checkbox:checked').length > 0 ) {
				return $(this).attr('data-item-name');
			}
		}).get();
	}

	render_result_list() {
		const me = this;
		let checked = this.get_checked_values();

		this.items
			.filter(result => !checked.includes(result.name))
			.forEach(result => {
				me.$items.append(me.make_list_row(result));
			});

		if (frappe.flags.auto_scroll) {
			this.$items.animate({scrollTop: me.$items.prop('scrollHeight')}, 500);
		}
	}

	bind_events() {
		const me = this;
		this.$items.on('click', '.list-item-container', function (e) {
			if (!$(e.target).is(':checkbox') && !$(e.target).is('a')) {
				me.$items.find(':checkbox').prop("checked", false);
				$(this).find(':checkbox').trigger('click');
			}
		});
	}

}