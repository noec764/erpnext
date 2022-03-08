frappe.listview_settings['Customer'] = {
	add_fields: ["customer_name", "territory", "customer_group", "customer_type", "image"],
	get_indicator: function(doc) {
		var status_color = {
			"Disabled": "gray",
			"Enabled": "green",
			"Subscriber": "blue",
		};
		return [__(doc.status), status_color[doc.status], "status,=,"+doc.status];
	},
};
