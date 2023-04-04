// Copyright (c) 2019, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Booking Calendar', {
	refresh(frm) {
		const $btn = frm.fields_dict.booking_calendar_setup_button.$input;
		$btn.removeClass("btn-default btn-primary").addClass(frm.doc.__islocal ? "btn-primary" : "btn-default");
	},
	booking_calendar_setup_button(frm) {
		const all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
		const defaults = {
			days: all_days.slice(0, 5),
			slots: [
				{ start_time: "08:00", end_time: "12:00" },
				{ start_time: "13:00", end_time: "18:00" },
			],
		};

		const dialog = new frappe.ui.Dialog({
			title: __("Setup Calendar"),
			fields: [
				{
					fieldtype: "MultiCheck",
					fieldname: "days",
					label: __("Days"),
					options: all_days.map(day => ({
						label: __(day),
						value: day,
						checked: defaults.days.includes(day),
					})),
				},
				{
					fieldtype: "Section Break",
				},
				{
					fieldtype: "Table",
					fieldname: "slots",
					label: __("Timeslots"),
					in_place_edit: true,
					fields: [
						{
							fieldtype: "Time",
							fieldname: "start_time",
							label: __("Start Time"),
							in_list_view: 1,
						},
						{
							fieldtype: "Time",
							fieldname: "end_time",
							label: __("End Time"),
							in_list_view: 1,
						},
					],
					data: defaults.slots,
				},
			],
			primary_action() {
				const values = dialog.get_values();
				const slots = values.days.flatMap(day => {
					return values.slots.map(slot => ({
						day: day,
						start_time: slot.start_time,
						end_time: slot.end_time,
					}));
				});
				frm.set_value("booking_calendar", slots)
				dialog.hide();
			}
		});
		dialog.show();
	}
});
