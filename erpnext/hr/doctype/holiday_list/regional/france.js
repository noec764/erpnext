// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Holiday List', {
	refresh: function(frm) {
		frm.add_custom_button(__("Add french bank holidays"), function() {
			frappe.xcall('erpnext.regional.france.bank_holidays.get_french_bank_holidays', {year: 2020, zone: "Métropole"})
			.then(r => {
				Object.keys(r).forEach(function(element) {
					const holiday = frm.add_child("holidays");
					holiday.holiday_date = r[element];
					holiday.description = element;
				});
				frm.refresh_field("holidays");
			})
		});
	}
});