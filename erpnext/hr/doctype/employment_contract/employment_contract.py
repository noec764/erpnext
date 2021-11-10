# Copyright (c) 2021, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.model.document import Document

class EmploymentContract(Document):
	def validate(self):
		self.weekly_working_hours = sum([
			flt(self.monday),
			flt(self.tuesday),
			flt(self.wednesday),
			flt(self.thursday),
			flt(self.friday),
			flt(self.satuday),
			flt(self.sunday)
		])
