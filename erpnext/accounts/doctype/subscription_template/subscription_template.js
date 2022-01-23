// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Subscription Template', {
	setup(frm) {
		frm.set_query('print_format', function() {
			return {
				filters: {
					"doc_type": "Sales Invoice",
					"disabled": 0
				}
			}
		});
	},
	refresh(frm) {
		frm.page.clear_actions_menu();
		if (!frm.is_new()) {
			frm.page.add_action_item(__('Make a subscription'), function() {
				frm.trigger('make_new_subscription');
			});
		}

		if (frm.is_new() && !frm.doc.print_format) {
			frappe.model.with_doctype("Sales Invoice", function() {
				frm.set_value("print_format", frappe.get_meta("Sales Invoice").default_print_format)
			});
		}
	},

	make_new_subscription(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __('Create a new subscription'),
			fields: [
				{
					"label" : "Company",
					"fieldname": "company",
					"fieldtype": "Link",
					"reqd": 1,
					"default": frappe.defaults.get_user_default("Company"),
					"options": "Company"
				},
				{
					"label" : "Customer",
					"fieldname": "customer",
					"fieldtype": "Link",
					"reqd": 1,
					"options": "Customer"
				},
				{
					"label" : "Start Date",
					"fieldname": "start_date",
					"fieldtype": "Date",
					"reqd": 1,
					"default": frappe.datetime.get_today()
				}
			],
			primary_action: function() {
				const values = dialog.get_values();
				const args = Object.assign(values, {"template": frm.doc.name})

				frappe.call({
					method: "erpnext.accounts.doctype.subscription_template.subscription_template.make_subscription",
					args: args,
				}).then(r => {
					if (r && !r.exc) {
						frappe.show_alert({message:__("The subscription has been created"), indicator:'green'});
						frm.reload_doc();
					} else {
						frappe.show_alert({message:__("An error prevented the subscription's creation"), indicator:'red'});
					}
				})
				dialog.hide()
			}
		})
		dialog.show()
	},

	payment_gateways_template(frm) {
		if(frm.doc.payment_gateways_template) {
			frappe.model.with_doc("Portal Payment Gateways Template", frm.doc.payment_gateways_template, function() {
				const template = frappe.get_doc("Portal Payment Gateways Template", frm.doc.payment_gateways_template)
				frm.doc.payment_gateways = []
				template.payment_gateways.slice().forEach(child => {
					frm.add_child('payment_gateways', {
						payment_gateway: child.payment_gateway
					});
					frm.refresh_fields("payment_gateways");
				})
			});
		}
	},
});
