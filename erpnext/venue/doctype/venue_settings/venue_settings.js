// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Venue Settings', {
	refresh: function(frm) {
		if (frm.doc.__onload && frm.doc.__onload.quotation_series) {
			let quotation_series = frm.doc.__onload.quotation_series;
			if (typeof quotation_series === 'string') {
				quotation_series = quotation_series.split('\n');
			}
			frm.fields_dict["cart_settings_overrides"].grid
				.update_docfield_property("quotation_series", "options", quotation_series);
		}

		if (!frm.is_new()) {
			frm.add_custom_button(__("Create/Update Role Profile Fields in Customer and Subscription"), function(){
				frappe.call({
					method: "erpnext.venue.doctype.venue_settings.venue_settings.create_role_profile_fields"
				}).then(r => {
					frappe.show_alert({
						message: __("A field called role_profile_name has been created in the Customer and Subscription document types"),
						indicator: "green"
					})
				})
			});
		}
	},
})

frappe.ui.form.on('Venue Cart Settings', {
	company(frm, cdt, cdn) {
		const row = locals[cdt][cdn]
		if (row && row.company) {
			const is_duplicate = frm.doc.cart_settings_overrides.some((row2) => {
				return row2.company === row.company && row2.name != row.name
			})
			if (is_duplicate) {
				row.company = ''
				frm.refresh_field('cart_settings_overrides')
				frappe.msgprint({
					title: __('{0} {1} already exists', [__('Company'), row.company]),
					indicator: 'orange',
				})
			}
		}
	},
	cart_settings_overrides_add(frm, cdt, cdn) {
		// When adding a row, set the company to the empty string
		const row = locals[cdt][cdn]
		row.company = ''
		row.default_customer_group = ''
		row.quotation_series = ''
		row.price_list = ''
		frm.refresh_field('cart_settings_overrides')
	},
})

frappe.tour['Venue Settings'] = [
	{
		fieldname: "minute_uom",
		title: __("Minute UOM"),
		description: __("Unit of measure corresponding to one minute"),
	},
	{
		fieldname: "clear_item_booking_draft_duration",
		title: __("Clear bookings in shopping cart after x minutes"),
		description: __("Time interval between the last modification of an item booking with status 'In Cart' and its automatic deletion."),
	},
	{
		fieldname: "enable_simultaneous_booking",
		title: __("Enable simultaneous booking"),
		description: __("Activates the possibility to set a number of allowed simultaneous bookings for each item in the item master data."),
	},
	{
		fieldname: "sync_with_google_calendar",
		title: __("Automatically synchronize with Google Calendar"),
		description: __("If checked, items booked on the portal will be automatically synchronized with Google Calendar."),
	},
]
