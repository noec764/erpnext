import frappe


def execute():
	for dt in ["Sales Invoice", "Purchase Invoice"]:
		for doc in frappe.get_all(
			dt,
			filters={"docstatus": (">", 0), "posting_date": (">", "2022-11-25")},
			fields=["name", "remarks"],
		):
			if "{{ doc.name }}" in doc.remarks:
				remarks = doc.remarks.replace("{{ doc.name }}", doc.name)
				frappe.db.set_value(dt, doc.name, "remarks", remarks)
