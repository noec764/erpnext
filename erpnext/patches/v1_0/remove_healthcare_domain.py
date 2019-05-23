from __future__ import unicode_literals
import frappe
from frappe import _

def execute():
	# Delete assigned roles
	roles = ["Healthcare Administrator", "LabTest Approver", "Laboratory User", "Nursing User", "Physician", "Patient"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabHas Role`
	WHERE 
		role in ({0})
	""".format(','.join(['%s']*len(roles))), tuple(roles))

	# Standard portal items
	titles = ["Personal Details", "Prescription", "Lab Test", "Patient Appointment", _("Personal Details"), _("Prescription"), \
		_("Lab Test"), _("Patient Appointment")]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabPortal Menu Item`
	WHERE 
		title in ({0})
	""".format(','.join(['%s']*len(titles))), tuple(titles))

	# Delete DocTypes, Pages, Reports, Roles, Domain and Custom Fields
	elements = [
		{"document": "DocType", "items": [x["name"] for x in frappe.get_all("DocType", filters={"module": "Healthcare"})]},
		{"document": "Report", "items": ["Lab Test Report"]},
		{"document": "Page", "items": ["appointment-analytic", "medical_record"]},
		{"document": "Web Form", "items": ["lab-test", "patient-appointments", "personal-details", "prescription"]},
		{"document": "Print Format", "items": ["Encounter Print", "Lab Test Print", "Sample ID Print"]},
		{"document": "Role", "items": roles},
		{"document": "Domain", "items": ["Healthcare"]},
		{"document": "Module Def", "items": ["Healthcare"]},
		{"document": "Custom Field", "items": ["Sales Invoice-patient", "Sales Invoice-patient_name", "Sales Invoice-ref_practitioner", \
			"Sales Invoice Item-reference_dt", "Sales Invoice Item-reference_dn"]},
		{"document": "Item Group", "items": [_('Laboratory'), _('Drug')]}
	]

	for element in elements:
		for item in element["items"]:
			try:
				frappe.delete_doc(element["document"], item)
			except Exception as e:
				print(e)

	# Delete Desktop Icons
	desktop_icons = ["Patient", "Patient Appointment", "Patient Encounter", "Lab Test", "Healthcare", "Vital Signs", "Clinical Procedure", "Inpatient Record"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabDesktop Icon`
	WHERE 
		module_name in ({0})
	""".format(','.join(['%s']*len(desktop_icons))), tuple(desktop_icons))