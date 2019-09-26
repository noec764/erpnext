// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Booking', {
	refresh: function(frm) {
		if (frm.doc.docstatus == 1) {
			if (!frm.doc.reference_name) {
				if (frm.doc.billing_qty && frm.doc.sales_uom && frm.doc.party_type && frm.doc.party_name) {
					frm.page.add_action_item(__("Create a quotation"), () => {
						frappe.xcall(
							"erpnext.stock.doctype.item_booking.item_booking.make_quotation",
							{ source_name: frm.doc.name }
						).then(r => {
							if (r) {
								frm.reload_doc();
								frappe.set_route('Form', r.doctype, r.name);
							}
						})
					})
				}
			}
		}

		frm.set_query('party_type', () => {
			return {
				filters: {
					name: ['in', ['Lead', 'Customer']]
				}
			};
		});

		frm.set_query('sales_uom', () => {
			return {
				query:"erpnext.accounts.doctype.pricing_rule.pricing_rule.get_item_uoms",
				filters: {'value': frm.doc.item, apply_on: 'Item Code'}
			}
		})
	}
});
