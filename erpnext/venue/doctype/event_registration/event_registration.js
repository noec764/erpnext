// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Event Registration", {
	onload(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Sales Invoice", "Archived Document"]
	},
	refresh(frm) {
		if (!frm.doc.__islocal && frm.doc.amount) {
			// Registration is created and payable

			const is_cancelled = frm.doc.docstatus == 2
			const is_unpaid = frm.doc.payment_status.match(/^(|Unpaid|Pending)$/)
			const is_paid = frm.doc.payment_status === "Paid"

			if (!is_cancelled && is_unpaid) {
				// Registration is not yet paid, so an invoice can be created.
				const msg = __("Submit then create draft invoice", null, "Event Registration")
				frm.page.set_primary_action(msg, () => {
					frappe.model.open_mapped_doc({
						method: "erpnext.venue.doctype.event_registration.event_registration.submit_then_make_invoice",
						frm: frm,
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
						frm.reload_doc();
					});
				});
			}

			frm.trigger("show_linked_invoices");
		}
	},
	show_linked_invoices(frm) {
		frappe.call(
			"erpnext.venue.doctype.event_registration.event_registration.get_linked_invoices",
			{ name: frm.doc.name },
		).then((r) => {
			if (r.exc || (!r.message) || (!r.message.length)) return;

			const div = document.createElement("div");
			Object.assign(div.style, {
				display: "flex",
				flexDirection: "column",
			});
			for (const obj of r.message) {
				if (!obj || !("doctype" in obj) || !("name" in obj)) {
					console.warn("Invalid value:", obj);
					continue;
				}

				const href = frappe.utils.get_form_link(obj.doctype, obj.name, false /* no html */);
				const row = document.createElement("a");
				row.style.display = "block";
				row.append(
					__(obj.doctype, null, obj.doctype),
					" · ",
					obj.name,
				)
				row.setAttribute("href", href);
				div.appendChild(row);
			}
			const html = div.innerHTML;
			cur_frm.dashboard.add_section(html, __("Invoices"));
		});
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
