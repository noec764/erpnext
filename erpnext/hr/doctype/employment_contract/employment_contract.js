// Copyright (c) 2021, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Employment Contract', {
	weekly_working_hours(frm) {
		if (!frm.from_daily_time) {
			const divided_time = frm.doc.weekly_working_hours ? flt(frm.doc.weekly_working_hours) / 5 : 0
			const week_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
			week_days.forEach(d => {
				frm.from_weekly_time = true
				frm.set_value(d, divided_time).then(() => {
					frm.from_weekly_time = false
				})
			})
		}
	},
	monday(frm) {
		frm.trigger("recalculate_working_hours");
	},
	tuesday(frm) {
		frm.trigger("recalculate_working_hours");
	},
	wednesday(frm) {
		frm.trigger("recalculate_working_hours");
	},
	thursday(frm) {
		frm.trigger("recalculate_working_hours");
	},
	friday(frm) {
		frm.trigger("recalculate_working_hours");
	},
	saturday(frm) {
		frm.trigger("recalculate_working_hours");
	},
	sunday(frm) {
		frm.trigger("recalculate_working_hours");
	},
	recalculate_working_hours(frm) {
		if (!frm.from_weekly_time) {
			const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
			const total = days.reduce((prev, value) => {
				return flt(prev) + flt(frm.doc[value])
			}, 0)

			frm.from_daily_time = true
			frm.set_value("weekly_working_hours", total).then(() => {
				frm.from_daily_time = false
			})
		}
	}
});
