// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Event Slot', {
	event: function(frm) {
		if (frm.doc.event && !frm.doc.starts_on) {
			frappe.db.get_value("Event", frm.doc.event, ["starts_on", "ends_on"], r => {
				frm.set_value("starts_on", r.starts_on);
				frm.set_value("ends_on", r.ends_on);
			})
		}
	}
});
