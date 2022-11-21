import frappe


def execute():
	for lead in frappe.get_all("Lead", dict(docstatus=1)):
		frappe.db.set_value("Lead", lead.name, "docstatus", 0)
