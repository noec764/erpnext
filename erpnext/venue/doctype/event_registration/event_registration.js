// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Event Registration", {
	refresh(frm) {
		if (!frm.doc.__islocal && frm.doc.amount) {
			// Registration is created and payable

			const is_cancelled = frm.doc.docstatus == 2
			const is_unpaid = frm.doc.payment_status.match(/^(|Unpaid|Pending)$/)
			const is_paid = frm.doc.payment_status === "Paid"

			if (!is_cancelled && is_unpaid) {
				// Registration is not yet paid, so an invoice can be created.
				const msg = __("Submit then create draft invoice", null, "Event Registration")
				frm.add_custom_button(msg, () => {
					return frm.call("api_submit_then_make_invoice").then((r) => {
						const si = r.message
						frappe.set_route("Form", si.doctype, si.name)
					});
				});
			}

			if (is_cancelled && is_paid) {
				// Registration was paid by the client, but then cancelled
				const msg = __("Mark as {0}", [__("Refunded", null, "Event Registration")])
				frm.add_custom_button(msg, () => {
					return frappe.call(
						"erpnext.venue.doctype.event_registration.event_registration.mark_as_refunded",
						{ name: frm.doc.name },
					).then(() => {
						cur_frm.reload_doc();
					});
				});
			}
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
