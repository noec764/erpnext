# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import format_date, getdate


class LeavePeriod(Document):
	def validate(self):
		self.validate_dates()
		self.title = f"{format_date(self.from_date)}-{format_date(self.to_date)}"

	def validate_dates(self):
		if getdate(self.from_date) >= getdate(self.to_date):
			frappe.throw(_("To date can not be equal or less than from date"))
