import frappe


def execute():
	item = frappe.db.get_value("Portal Menu Item", {"route": "/subscription"})
	if item:
		frappe.delete_doc("Portal Menu Item", item)
