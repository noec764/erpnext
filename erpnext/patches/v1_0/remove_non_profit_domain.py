from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc('website', 'doctype', 'portal_settings')
	# Delete assigned roles
	roles = ["Non Profit Manager", "Non Profit Member", "Non Profit Portal User"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabHas Role`
	WHERE 
		role in ({0})
	""".format(','.join(['%s']*len(roles))), tuple(roles))

	# Standard portal items
	titles = ["Certification", _("Certification")]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabPortal Menu Item`
	WHERE 
		title in ({0})
	""".format(','.join(['%s']*len(titles))), tuple(titles))

	# Delete DocTypes, Pages, Reports, Roles, Domain and Custom Fields
	elements = [
		{"document": "DocType", "items": [x["name"] for x in frappe.get_all("DocType", filters={"module": "Non Profit"})]},
		{"document": "Report", "items": ["Expiring Memberships"]},
		{"document": "Role", "items": roles},
		{"document": "Domain", "items": ["Non Profit"]},
		{"document": "Module Def", "items": ["Non Profit"]},
		{"document": "Web Form", "items": ["certification-application", "certification-application-usd", "grant-application"]}
	]

	for element in elements:
		for item in element["items"]:
			try:
				frappe.delete_doc(element["document"], item)
			except Exception as e:
				print(e)

	# Delete Desktop Icons
	desktop_icons = ["Non Profit", "Member", "Donor", "Volunteer", "Grant Application"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabDesktop Icon`
	WHERE 
		module_name in ({0})
	""".format(','.join(['%s']*len(desktop_icons))), tuple(desktop_icons))