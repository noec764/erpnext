// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Subscription Plan', {
	onload: function(frm) {
		frm.set_query('uom', function(doc) {
			return {
				query:"erpnext.accounts.doctype.pricing_rule.pricing_rule.get_item_uoms",
				filters: {value: frm.doc.item, apply_on: 'Item Code'}
			}
		});
	},
	price_determination: function(frm) {
		frm.toggle_reqd("cost", frm.doc.price_determination === 'Fixed rate');
	},
});