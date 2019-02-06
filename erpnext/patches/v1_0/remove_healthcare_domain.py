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
	titles = ["Personal Details", "Prescription", "Lab Test", "Patient Appointment"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabPortal Menu Item`
	WHERE 
		title in ({0})
	""".format(','.join(['%s']*len(titles))), tuple(titles))

	# Delete DocTypes, Pages, Reports, Roles, Domain and Custom Fields
	elements = [
		{"document": "DocType", "items": ["Antibiotic", "Appointment Type", "Clinical Procedure", "Clinical Procedure Item", "Clinical Procedure Template", \
			"Codification Table", "Complaint", "Diagnosis", "Dosage Form", "Dosage Strength", "Drug Prescription", "Fee Validity", "Healthcare Practitioner", \
			"Healthcare Schedule Time Slot", "Healthcare Service Unit", "Healthcare Service Unit Type", "Healthcare Settings", "Inpatient Occupancy", "Inpatient Record", \
			"Lab Prescription", "Lab Test", "Lab Test Groups", "Lab Test Sample", "Lab Test Template", "Lab Test UOM", "Medical Code", "Medical Code Standard", \
			"Medical Department", "Normal Test Items", "Normal Test Template", "Patient", "Patient Appointment", "Patient Encounter", "Patient Medical Record", \
			"Patient Relation", "Practitioner Schedule", "Practitioner Service Unit Schedule", "Prescription Dosage", "Prescription Duration", "Procedure Prescription", \
			"Sample Collection", "Sensitivity", "Sensitivity Test Items", "Special Test Items", "Special Test Template", "Vital Signs"]},
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
				print(item)
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