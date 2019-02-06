from __future__ import unicode_literals
import frappe

def execute():
	elements = [
		{"document": "DocType", "items": ["Hotel Room", "Hotel Room Amenity", "Hotel Room Package", "Hotel Room Pricing", "Hotel Room Pricing Item", "Hotel Room Pricing Package", \
			"Hotel Room Reservation", "Hotel Room Reservation Item", "Hotel Room Type", "Hotel Settings"]},
		{"document": "DocType", "items": ["Restaurant", "Restaurant Menu", "Restaurant Menu Item", "Restaurant Order Entry", "Restaurant Order Entry Item", \
			"Restaurant Reservation", "Restaurant Table"]},
		{"document": "Report", "items": ["Hotel Room Occupancy"]},
		{"document": "Role", "items": ["Hotel Manager", "Hotel Reservation User"]},
		{"document": "Role", "items": ["Restaurant Manager"]},
		{"document": "Domain", "items": ["Hospitality"]},
		{"document": "Custom Field", "items": ["Sales Invoice-restaurant", "Sales Invoice-restaurant_table", "Price List-restaurant_menu"]}
	]

	for element in elements:
		for item in element["items"]:
			try:
				print(item)
				frappe.delete_doc(element["document"], item)
			except Exception as e:
				print(e)


	desktop_icons = ["Hotels", "Restaurant"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabDesktop Icon`
	WHERE 
		module_name like '%s'
	""", desktop_icons)