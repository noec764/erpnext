from __future__ import unicode_literals
import frappe

def execute():
	elements = [
		{"document": "DocType", "items": ["Certification Application", "Certified Consultant", "Chapter", "Chapter Member", "Donor", "Donor Type", \
			"Grant Application", "Member", "Membership", "Membership Type", "Volunteer", "Volunteer Skill", "Volunteer Type"]},
		{"document": "Report", "items": ["Expiring Memberships"]},
		{"document": "Role", "items": ["Non Profit Manager", "Non Profit Member", "Non Profit Portal User"]},
		{"document": "Domain", "items": ["Non Profit"]},
		{"document": "Web Form", "items": ["certification-application", "certification-application-usd", "grant-application"]}
	]

	for element in elements:
		for item in element["items"]:
			try:
				print(item)
				frappe.delete_doc(element["document"], item)
			except Exception as e:
				print(e)


	desktop_icons = ["Non Profit", "Member", "Donor", "Volunteer", "Grant Application"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabDesktop Icon`
	WHERE 
		module_name like '%s'
	""", desktop_icons)