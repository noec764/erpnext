// Copyright (c) 2021, Dokos and contributors
// For license information, please see license.txt

frappe.ui.form.EventSlotBookingQuickEntryForm = class EventSlotBookingQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	set_meta_and_mandatory_fields() {
		super.set_meta_and_mandatory_fields();

		this.mandatory.map(m => {
			if (m.fieldname == "user") {
				m.get_query = function() {
					return {
						query: "frappe.core.doctype.user.user.user_query",
						filters: {
							ignore_user_type: 1
						}
					};
				}
			}
		})
	}
}