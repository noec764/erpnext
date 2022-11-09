// Copyright (c) 2020, Dokos and Contributors
// License: See license.txt

frappe.ui.form.on('Event', {
	setup(frm) {
		frm.custom_make_buttons = {
			'Item Booking': 'Book an item'
		}
	},
	refresh(frm) {
		frm.trigger('add_item_booking_details')
		if (!frm.is_new()) {
			frm.add_custom_button(__('Book an item'), function () {
				itemBookingDialog(frm)
			});
		}
	},
	add_item_booking_details(frm) {
		frappe.model.with_doctype("Item Booking", () => {
			frappe.db.get_list('Item Booking', {filters: {event: frm.doc.name}, fields: ["name", "item_name", "color", "starts_on", "status"]}).then(data => {
				if (data.length) {
					const item_booking_section = data.map(d => {
						let indicator = frappe.get_indicator(d)
						let color = (indicator && indicator.length) ? frappe.ui.color.get_color(indicator[1]) : d.color;
						if (Array.isArray(color)) {
							color = color[color.length - 1]
						}
						const $card = $(`
							<div class="item-booking-card">
								<div class="flex align-items-center">
									<div class="left-title">${frappe.datetime.obj_to_user(d.starts_on).replace(new RegExp('[^\.]?' + moment(d.starts_on).format('YYYY') + '.?'), '')}</div>
									<div class="right-body">
										<div style="color: ${d.color};">${d.item_name}</div>
										<div class="small" style="color: ${color};">${__(d.status)}</div>
									</div>
								</div>
							</div>
						`)

						$card.on("click", () => {
							frappe.set_route("Form", "Item Booking", d.name)
						})

						return $card
					})
					$(".custom").remove();
					frm.dashboard.add_section(item_booking_section).removeClass("form-dashboard-section");
				}
			})
		})
	}
});

const itemBookingDialog = frm => {
	const d = new frappe.ui.form.MultiSelectDialog({
		doctype: "Item",
		target: "Item Booking",
		setters: [
			{
				"fieldname": "item_name",
				"fieldtype": "Data",
				"hidden": 1
			},
			{
				"fieldname": "enable_item_booking",
				"fieldtype": "Check",
				"value": 1,
				"hidden": 1
			}
		],
		primary_action_label: __("Book Item·s"),
		action: function(selections) {
			const values = selections;
			if(values.length === 0){
				frappe.msgprint(__("Please select at least one item"))
				return;
			}
			book_items(frm, values)
			d.dialog.hide();
		},
	});
}

const book_items = (frm, values) => {
	const promises = []
	values.forEach(value => {
		promises.push(new_booking(frm, value))
	})

	Promise.all(promises).then(r => {
		frm.refresh();
	})
}

const new_booking = (frm, value) => {
	return frappe.xcall('erpnext.venue.doctype.item_booking.item_booking.book_new_slot', {
		item: value,
		start: frm.doc.starts_on,
		end: frm.doc.ends_on,
		status: "Not confirmed",
		event: frm.doc.name,
		all_day: frm.doc.all_day
	})
}