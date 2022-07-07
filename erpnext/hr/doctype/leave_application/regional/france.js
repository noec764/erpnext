frappe.ui.form.on("Leave Application", {
	refresh: function(frm) {
		frm.get_field("from_date").set_label(__("Last working day before leave"))
		frm.get_field("to_date").set_label(__("First working day after leave"))
	}
})
