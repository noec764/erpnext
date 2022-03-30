# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document


class ProjectType(Document):
	def validate(self):
		if self.is_default:
			for project_type in frappe.get_all(
				"Project Type", filters={"is_default": 1, "name": ("!=", self.name)}
			):
				frappe.db.set_value("Project Type", project_type.name, "is_default", 0)
