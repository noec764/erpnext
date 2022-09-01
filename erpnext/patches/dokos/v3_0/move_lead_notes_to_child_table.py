import frappe


def execute():
	if frappe.db.has_column("Lead", "notes"):
		for lead in frappe.get_all("Lead", filters={"notes": ("is", "set")}, fields=["notes", "name"]):
			note = lead.notes
			frappe.db.set_value("Lead", lead.name, "notes", None)
			doc = frappe.get_doc("Lead", lead.name)
			doc.append("notes", {"note": note})
			doc.save()
