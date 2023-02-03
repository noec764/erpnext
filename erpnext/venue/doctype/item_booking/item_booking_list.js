frappe.listview_settings['Item Booking'] = {
	get_indicator: function(doc) {
		if (doc.status == "Confirmed") {
			return [__("Confirmed"), "green", "status,=,Confirmed"];
		} else if (doc.status == "Cancelled") {
			return [__("Cancelled"), "red", "status,=,Cancelled"];
		} else if (doc.status == "In cart") {
			return [__("In cart"), "orange", "status,=,In cart"];
		} else if (doc.status == "Not confirmed") {
			return [__("Not confirmed"), "grey", "status,=,Not confirmed"];
		}
	},
	onload: function(list_view) {
		if (list_view.page.fields_dict.user) {
			list_view.page.fields_dict.user.get_query = function() {
				return {
					query: "frappe.core.doctype.user.user.user_query",
					filters: {ignore_user_type: 1}
				}
			};
		}
	}
};