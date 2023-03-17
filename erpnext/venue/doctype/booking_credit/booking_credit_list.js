frappe.listview_settings['Booking Credit'] = {
	get_indicator: function(doc) {
		if (doc.status == "Draft") {
			return [__("Draft"), "red", "status,=,Draft"];
		} else if (doc.status == "Active") {
			return [__("Active"), "green", "status,=,Active"];
		} else if (doc.status == "Expired") {
			return [__("Expired"), "darkgray", "status,=,Expired"];
		} else if (doc.status == "Consumed") {
			return [__("Consumed"), "gray", "status,=,Consumed"];
		}
	}
};