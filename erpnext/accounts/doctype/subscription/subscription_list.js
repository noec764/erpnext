frappe.listview_settings['Subscription'] = {
	get_indicator: function(doc) {
		if(doc.status === 'Trial') {
			return [__("Trial"), "orange"];
		} else if(doc.status === 'Active') {
			return [__("Active"), "blue"];
		} else if(doc.status === 'Past Due Date') {
			return [__("Past Due Date"), "orange"];
		} else if(doc.status === 'Unpaid') {
			return [__("Unpaid"), "red"];
		} else if(doc.status === 'Paid') {
			return [__("Paid"), "green"];
		} else if(doc.status === 'Cancelled') {
			return [__("Cancelled"), "darkgrey"];
		}
	}
};
