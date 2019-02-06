from __future__ import unicode_literals
import frappe

def execute():
	# Delete assigned roles
	roles = ["Hotel Manager", "Hotel Reservation User", "Restaurant Manager"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabHas Role`
	WHERE 
		role in ({0})
	""".format(','.join(['%s']*len(roles))), tuple(roles))

	# Delete DocTypes, Pages, Reports, Roles, Domain and Custom Fields
	elements = [
		{"document": "DocType", "items": ["Hotel Room", "Hotel Room Amenity", "Hotel Room Package", "Hotel Room Pricing", "Hotel Room Pricing Item", "Hotel Room Pricing Package", \
			"Hotel Room Reservation", "Hotel Room Reservation Item", "Hotel Room Type", "Hotel Settings"]},
		{"document": "DocType", "items": ["Restaurant", "Restaurant Menu", "Restaurant Menu Item", "Restaurant Order Entry", "Restaurant Order Entry Item", \
			"Restaurant Reservation", "Restaurant Table"]},
		{"document": "Report", "items": ["Hotel Room Occupancy"]},
		{"document": "Role", "items": roles},
		{"document": "Domain", "items": ["Hospitality"]},
		{"document": "Module Def", "items": ["Restaurant", "Hotels"]},
		{"document": "Custom Field", "items": ["Sales Invoice-restaurant", "Sales Invoice-restaurant_table", "Price List-restaurant_menu"]}
	]

	for element in elements:
		for item in element["items"]:
			try:
				frappe.delete_doc(element["document"], item)
			except Exception as e:
				print(e)

	# Delete Desktop Icons
	desktop_icons = ["Hotels", "Restaurant"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabDesktop Icon`
	WHERE 
		module_name in ({0})
	""".format(','.join(['%s']*len(desktop_icons))), tuple(desktop_icons))