# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BookingCreditType(Document):
	def validate(self):
		self.validate_conversions()

	def validate_conversions(self):
		convertible_items = []
		for conversion in self.conversion_table:
			if conversion.item in convertible_items:
				self.remove(conversion)
				continue
			convertible_items.append(conversion.item)
