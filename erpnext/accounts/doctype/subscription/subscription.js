// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Subscription', {
	refresh: function(frm) {
		if(!frm.is_new()){
			frm.page.clear_actions_menu();
			if(frm.doc.status !== 'Cancelled'){
				frm.page.add_action_item(
					__('Cancel Subscription'),
					() => frm.events.cancel_this_subscription(frm)
				);
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

			frm.set_df_property("start", "read_only", 1);
			frm.set_df_property("trial_period_start", "read_only", 1);
			frm.set_df_property("trial_period_end", "read_only", 1);

			frappe.xcall("erpnext.accounts.doctype.subscription.subscription.subscription_headline", {
				'name': frm.doc.name
			})
			.then(r => {
				frm.dashboard.set_headline_alert(r);
			})
		} else {
			frm.set_df_property("change_start_trial", "hidden", 1);
		}
	},

	cancel_this_subscription: function(frm) {
		const doc = frm.doc;
		frappe.confirm(
			__('This action will stop future billing. Are you sure you want to cancel this subscription?'),
			function() {
				frappe.call({
					method:
					"erpnext.accounts.doctype.subscription.subscription.cancel_subscription",
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

	renew_this_subscription: function(frm) {
		const doc = frm.doc;
		frappe.confirm(
			__('You will lose records of previously generated invoices. Are you sure you want to restart this subscription?'),
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
	},

	change_start_trial: function(frm) {
		frm.set_df_property("start", "read_only", 0);
		frm.set_df_property("trial_period_start", "read_only", 0);
		frm.set_df_property("trial_period_end", "read_only", 0);
	}
});
