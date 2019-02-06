from __future__ import unicode_literals
import frappe
from frappe import _

def execute():
	# Delete assigned roles
	roles = ["Student", "Instructor", "Academics User", "Education Manager"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabHas Role`
	WHERE 
		role in ({0})
	""".format(','.join(['%s']*len(roles))), tuple(roles))

	# Standard portal items
	titles = ["Fees", "Admission", _("Fees"), _("Admission")]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabPortal Menu Item`
	WHERE 
		title in ({0})
	""".format(','.join(['%s']*len(titles))), tuple(titles))

	# Delete DocTypes, Pages, Reports, Roles, Domain and Custom Fields
	elements = [
		{"document": "DocType", "items": ["Academic Term", "Academic Year", "Assessment Criteria", "Assessment Criteria Group", "Assessment Group", "Assessment Plan", \
			"Assessment Plan Criteria", "Assessment Result", "Assessment Result Detail", "Assessment Result Tool", "Course", "Course Assessment Criteria", \
			"Course Schedule", "Course Scheduling Tool", "Education Settings", "Fee Category", "Fee Component", "Fee Schedule", "Fee Schedule Program", "Fee Schedule Student Group", \
			"Fee Structure", "Fees", "Grading Scale", "Grading Scale Interval", "Guardian", "Guardian Interest", "Guardian Student", "Instructor", "Instructor Log", \
			"Program", "Program Course", "Program Enrollment", "Program Enrollment Course", "Program Enrollment Fee", "Program Enrollment Tool", "Program Enrollment Tool Student", \
			"Program Fee", "Room", "School House", "Student", "Student Admission", "Student Admission Program", "Student Applicant", "Student Attendance", "Student Attendance Tool", \
			"Student Batch Name", "Student Category", "Student Group", "Student Group Creation Tool", "Student Group Creation Tool Course", "Student Group Instructor", \
			"Student Group Student", "Student Guardian", "Student Language", "Student Leave Application", "Student Log", "Student Report Generation Tool", "Student Sibling", "Student Siblings"]},
		{"document": "Report", "items": ["Absent Student Report", "Assessment Plan Status", "Course wise Assessment Report", "Final Assessment Grades", \
			"Student and Guardian Contact Details", "Student Batch-Wise Attendance", "Student Fee Collection", "Student Monthly Attendance Sheet"]},
		{"document": "Web Form", "items": ["student-applicant"]},
		{"document": "Role", "items": roles},
		{"document": "Domain", "items": ["Education"]},
		{"document": "Module Def", "items": ["Education"]},
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
	desktop_icons = ["Student", "Program", "Course", "Student Group", "Instructor", "Fees"]

	frappe.db.sql("""
	DELETE
	FROM 
		`tabDesktop Icon`
	WHERE 
		module_name in ({0})
	""".format(','.join(['%s']*len(desktop_icons))), tuple(desktop_icons))