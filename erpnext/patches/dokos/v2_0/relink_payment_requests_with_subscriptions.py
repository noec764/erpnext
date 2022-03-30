import frappe


def execute():
	frappe.reload_doc("accounts", "doctype", "Payment Request")

	for pr in frappe.get_all(
		"Payment Request",
		filters={"reference_doctype": "Subscription"},
		fields=["name", "reference_name"],
	):
		frappe.db.set_value("Payment Request", pr.name, "subscription", pr.reference_name)
