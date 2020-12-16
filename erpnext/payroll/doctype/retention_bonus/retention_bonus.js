// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Retention Bonus', {
	setup: function(frm) {
		frm.set_query("employee", function() {
			if (!frm.doc.company) {
				frappe.msgprint(__("Please Select Company First"));
			}
			return {
				filters: {
					"status": "Active",
					"company": frm.doc.company
				}
			};
		});

		frm.set_query("salary_component", function() {
			return {
				filters: {
					"type": "Earning"
				}
			};
		});
	}
});
