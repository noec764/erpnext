// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Subscription', {
	refresh: function(frm) {
		frm.page.clear_actions_menu();
		if(!frm.is_new()){
			if(frm.doc.status !== 'Cancelled'){
				if(!frm.doc.generate_invoice_at_period_start || !frm.doc.cancel_at_period_end){
					frm.page.add_action_item(
						__('Cancel Subscription'),
						() => frm.events.cancel_this_subscription(frm)
					);
				}
				frm.page.add_action_item(
					__('Fetch Subscription Updates'),
					() => frm.events.get_subscription_updates(frm)
				);

			}
			else if(frm.doc.status === 'Cancelled'){
				frm.page.add_action_item(
					__('Restart Subscription'),
					() => frm.events.renew_this_subscription(frm)
				);
			}

			frappe.xcall("erpnext.accounts.doctype.subscription.subscription.subscription_headline", {
				'name': frm.doc.name
			})
			.then(r => {
				frm.dashboard.clear_headline();
				frm.dashboard.set_headline_alert(r);
			})
		}
		frm.set_value("company", frappe.defaults.get_user_default("Company"));
	},

	cancel_this_subscription: function(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Cancel subscription"),
			fields: [
				{"fieldtype": "Date",
				"label": __("Cancellation date"),
				"fieldname": "cancellation_date",
				},
				{"fieldtype": "Check",
				"label": __("Prorate last invoice"),
				"fieldname": "prorate_invoice"
				}
			],
			primary_action: function() {
				const values = dialog.get_values();
				values["name"] = frm.doc.name
				dialog.hide()
				frappe.call({
					method:
					"erpnext.accounts.doctype.subscription.subscription.cancel_subscription",
					args: values,
					callback: function(data){
						if(!data.exc){
							frm.reload_doc();
						}
					}
				});
			}
		})
		dialog.show()
	},

	renew_this_subscription: function(frm) {
		const doc = frm.doc;
		frappe.confirm(
			__('Are you sure you want to restart this subscription?'),
			function() {
				frappe.call({
					method:
					"erpnext.accounts.doctype.subscription.subscription.restart_subscription",
					args: {name: doc.name},
					callback: function(data){
						if(!data.exc){
							frm.reload_doc();
						}
					}
				});
			}
		);
	},

	get_subscription_updates: function(frm) {
		const doc = frm.doc;
		frappe.call({
			method:
			"erpnext.accounts.doctype.subscription.subscription.get_subscription_updates",
			args: {name: doc.name},
			freeze: true,
			callback: function(data){
				if(!data.exc){
					frm.reload_doc();
				}
			}
		});
	}
});
