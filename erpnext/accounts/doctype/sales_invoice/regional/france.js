frappe.ui.form.on('Sales Invoice', {
	refresh(frm) {
		if (frm.docstatus == 0) {
			frm.trigger("validate_invoice_number");
		}
	},

	set_posting_time(frm) {
		frm.trigger("validate_invoice_number");
	},

	validate_invoice_number(frm) {
		frappe.db.get_list("Sales Invoice", {filters: {naming_series: frm.doc.naming_series}, fields: ["name", "posting_date", "posting_time"], order_by: "name desc", limit:1})
		.then(r => {
			if (r.length) {
				const posting_datetime = frappe.datetime.get_datetime_as_string(r[0].posting_date + " " + r[0].posting_time)
				const message = __("Please select a posting date and time after {0}", [frappe.datetime.str_to_user(posting_datetime)])
				frm.get_field("posting_date").set_description(message)
			}
		})
	}
})