import frappe


def execute():
	if frappe.db.get_single_value(
		"Website Settings", "website_theme"
	) == "Standard" and frappe.db.exists("Website Theme", "Dokos"):
		frappe.db.set_value("Website Settings", "Website Settings", "website_theme", "Dokos")
