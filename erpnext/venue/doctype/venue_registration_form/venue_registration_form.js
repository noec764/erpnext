// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Venue Registration Form', {
	refresh: function(frm) {
		if (frm.doc.status == "Pending") {
			frm.set_read_only();
		}
	}
});
