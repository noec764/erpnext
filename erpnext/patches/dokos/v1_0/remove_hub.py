import frappe


def execute():
	# Delete DocTypes, Pages, Reports, Roles, Domain and Custom Fields
	elements = [
		{
			"document": "DocType",
			"items": [x["name"] for x in frappe.get_all("DocType", filters={"module": "Hub Node"})],
		},
		{"document": "Module Def", "items": ["Hub Node"]},
	]

	for element in elements:
		for item in element["items"]:
			try:
				frappe.delete_doc(element["document"], item)
			except Exception as e:
				print(e)

	# Delete Desktop Icons
	desktop_icons = ["Student", "Program", "Course", "Student Group", "Instructor", "Fees"]

	frappe.db.sql(
		"""
	DELETE
	FROM
		`tabDesktop Icon`
	WHERE
		module_name in ({0})
	""".format(
			",".join(["%s"] * len(desktop_icons))
		),
		tuple(desktop_icons),
	)
