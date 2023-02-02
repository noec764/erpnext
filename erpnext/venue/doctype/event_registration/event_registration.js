// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Event Registration", {
	refresh(frm) {
		if (frm.doc.docstatus == 2 && frm.doc.payment_status == "Paid") {
			frm.add_custom_button(__('Mark as refunded'), () => {
				return frappe.call({
					method: "erpnext.venue.doctype.event_registration.event_registration.mark_registration_as_refunded",
					args: { name: frm.doc.name },
					freeze: true,
					callback() {
						cur_frm.reload_doc()
					}
				});
			});
		}
	}
});

frappe.tour["Event Registration"] = [
	{
		fieldname: "first_name",
		title: __("First name"),
		description: __("Indicate the first name of the person registering for the event."),
	},
	{
		fieldname: "last_name",
		title: __("Last name"),
		description: __("Indicate the last name of the person registering for the event."),
	},
	{
		fieldname: "email",
		title: __("Email"),
		description: __("Enter the email of the person registering for the event."),
	},
	{
		fieldname: "mobile_number",
		title: __("Mobile number"),
		description: __("Enter the mobile number of the person registering for the event."),
	},
	{
		fieldname: "event",
		title: __("event"),
		description: __("Choose the event that is relevant to the person's registration."),
	},
	{
		fieldname: "user",
		title: __("User"),
		description: __("Choose the user that is relevant to the person's registration."),
	},
	{
		fieldname: "contact",
		title: __("Contact"),
		description: __(
			"The contact will be assigned automatically if you have already set a user. However, you can also select a contact directly instead of a user."
		),
	},
];
