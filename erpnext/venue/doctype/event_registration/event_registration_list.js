frappe.listview_settings["Event Registration"] = {
	has_indicator_for_draft: true,
	has_indicator_for_cancelled: true,
	add_fields: ["docstatus", "payment_status"],
	hide_name_column: true,
	get_indicator(doc) {
		if (doc.docstatus == 1 && doc.payment_status == "Paid") {
			return [
				__("Paid", null, "Event Registration"),
				"green",
				"docstatus,=,1|payment_status,=,Paid"
			];
		}
		if (doc.docstatus == 1 && doc.payment_status == "") {
			return [
				__("Confirmed", null, "Event Registration"),
				"green",
				"docstatus,=,1|payment_status,=,"
			];
		}
		if (doc.docstatus == 2 && doc.payment_status == "Paid") {
			return [
				__("To refund", null, "Event Registration"),
				"blue",
				"docstatus,=,2|payment_status,=,Paid"
			];
		}
		if (doc.docstatus == 2 && doc.payment_status == "Refunded") {
			return [
				__("Refunded", null, "Event Registration"),
				"yellow",
				"docstatus,=,2|payment_status,=,Refunded"
			];
		}
		if (doc.docstatus == 2) {
			return [__("Cancelled"), "red", "docstatus,=,2"];
		}
		if (doc.docstatus == 0 && doc.payment_status) {
			const msg = __("{0}: {1}", [__("Draft"), __(doc.payment_status, null, "Event Registration")])
			return [msg , "grey", "docstatus,=,0|payment_status,=," + doc.payment_status];
		}
		if (doc.docstatus == 0) {
			return [__("Draft"), "grey", "docstatus,=,0"];
		}
	}
};