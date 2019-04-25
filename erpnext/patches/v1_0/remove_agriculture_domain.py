from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("Assets", "DocType", "Location")
	# Delete assigned roles
	roles = ["Agriculture Manager", "Agriculture User"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabHas Role`
	WHERE 
		role in ({0})
	""".format(','.join(['%s']*len(roles))), tuple(roles))

	# Delete DocTypes, Pages, Reports, Roles, Domain and Custom Fields
	elements = [
		{"document": "DocType", "items": ['Crop Cycle', 'Weather', 'Soil Texture', 'Water Analysis', \
			'Soil Analysis', 'Plant Analysis', 'Agriculture Task', 'Linked Location', \
			'Detected Disease', 'Agriculture Analysis Criteria', 'Disease', 'Crop', \
			'Weather Parameter', 'Soil Texture Criteria', 'Fertilizer', 'Linked Soil Texture', \
			'Water Analysis Criteria', 'Soil Analysis Criteria', 'Plant Analysis Criteria', \
			'Linked Soil Analysis', 'Linked Plant Analysis', 'Fertilizer Content', 'Land Unit']},
		{"document": "Role", "items": roles},
		{"document": "Domain", "items": ["Agriculture"]},
		{"document": "Module Def", "items": ["Agriculture"]},
		{"document": "Item Group", "items": ["Fertilizer", "Seed", "By-product", "Produce"]}
	]

	for element in elements:
		for item in element["items"]:
			try:
				frappe.delete_doc(element["document"], item)
			except Exception as e:
				print(e)

	# Delete Desktop Icons
	desktop_icons = [
		'Agriculture Task',
		'Crop',
		'Crop Cycle',
		'Fertilizer',
		'Item',
		'Location',
		'Disease',
		'Plant Analysis',
		'Soil Analysis',
		'Soil Texture',
		'Task',
		'Water Analysis',
		'Weather'
	]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabDesktop Icon`
	WHERE 
		module_name in ({0})
	""".format(','.join(['%s']*len(desktop_icons))), tuple(desktop_icons))
