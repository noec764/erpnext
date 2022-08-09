import frappe


def execute():
	for dt in ("Asset Finance Book", "Depreciation Schedule"):
		for line in frappe.get_all(dt, fields=["name", "depreciation_method"]):
			if line.depreciation_method == "Prorated Straight Line (360 Days)":
				frappe.db.set_value(dt, line.name, "depreciation_method", "Straight Line")
