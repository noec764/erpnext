// Copyright (c) 2021, Dokos and contributors
// For license information, please see license.txt

frappe.provide('frappe.ui.form');

frappe.ui.form.ShiftAssignmentQuickEntryForm = frappe.ui.form.QuickEntryForm.extend({
	set_meta_and_mandatory_fields: function() {
		this._super();

		this.mandatory.map(m => {
			if (m.options == "Department") {
				m.get_query = function() {
					return {
						filters: {
							"is_group": 0
						}
					};
				}
			}
		})
	}
})
