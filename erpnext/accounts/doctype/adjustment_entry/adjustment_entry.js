// Copyright (c) 2021, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Adjustment Entry', {
	get_documents(frm) {
		frappe.call({
			method: "erpnext.accounts.doctype.adjustment_entry.adjustment_entry.get_documents",
			args: {
				entry_type: frm.doc.entry_type,
				date: frm.doc.posting_date,
				company: frm.doc.company
			}
		}).then(r => {
			frm.clear_table('details')
			r.message.forEach((d) => {
				frm.add_child("details",d);
			});
			refresh_field("details");
		})
	}
});
