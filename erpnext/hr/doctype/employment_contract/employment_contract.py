# Copyright (c) 2021, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class EmploymentContract(Document):
	def validate(self):
		self.weekly_working_hours = self.weekly_working_hours or sum(
			[
				flt(self.monday),
				flt(self.tuesday),
				flt(self.wednesday),
				flt(self.thursday),
				flt(self.friday),
				flt(self.saturday),
				flt(self.sunday),
			]
		)
