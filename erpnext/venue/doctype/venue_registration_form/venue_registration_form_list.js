frappe.listview_settings['Venue Registration Form'] = {
	get_indicator: function(doc) {
		let color = "blue";
		if (doc.status == "Pending") {
			color = "orange";
		} else if (doc.status == "Abandonned") {
			color = "darkgray";
		} else if (doc.status == "Completed") {
			color = "green";
		}
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
	has_indicator_for_draft: true,
}