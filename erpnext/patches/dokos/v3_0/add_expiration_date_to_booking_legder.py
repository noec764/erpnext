import frappe


def execute():
	for doc in frappe.get_all(
		"Booking Credit Ledger",
		filters={"reference_doctype": "Booking Credit"},
		fields=["name", "reference_document"],
	):
		if expiration_date := frappe.db.get_value(
			"Booking Credit", doc.reference_document, "expiration_date"
		):
			frappe.db.set_value("Booking Credit Ledger", doc.name, "expiration_date", expiration_date)
