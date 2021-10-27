# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
import frappe
from frappe import _

class ProjectType(Document):
	def validate(self):
		if self.is_default:
			for project_type in frappe.get_all("Project Type", filters={"is_default": 1, "name": ("!=", self.name)}):
				frappe.db.set_value("Project Type", project_type.name, "is_default", 0)
