// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Booking Credit Type', {
	setup: function(frm) {
		frm.set_query("uom", "conversion_table", function(doc) {
			return {
				query: "erpnext.e_commerce.doctype.website_item.website_item.get_booking_uoms",
			};
		});

		frm.set_query("item", "conversion_table", function(doc) {
			return {
				"filters": {
					"enable_item_booking": 1
				}
			};
		});
	}
});
