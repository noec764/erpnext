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
			console.log(r.message)
			frm.clear_table('details')
			r.message.documents.forEach((d) => {
				frm.add_child("details",d);
			});
			frm.refresh_field("details");

			frm.set_value("total_debit", r.message.total_debit);
			frm.refresh_field("total_debit");;
			frm.set_value("total_credit", r.message.total_credit);
			frm.refresh_field("total_credit");
			frm.set_value("total_posting_amount", r.message.total_posting_amount);
			frm.refresh_field("total_posting_amount");
		})
	}
});
