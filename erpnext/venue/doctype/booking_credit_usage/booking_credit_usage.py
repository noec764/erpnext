# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry
from erpnext.venue.utils import get_customer


class BookingCreditUsage(Document):
	def validate(self):
		if not self.customer:
			self.customer = get_customer(self.user)

	def on_submit(self):
		create_ledger_entry(
			**{
				"user": self.user,
				"customer": self.customer,
				"date": self.datetime,
				"credits": self.quantity * -1,
				"reference_doctype": self.doctype,
				"reference_document": self.name,
				"uom": self.uom,
				"item": self.item,
			}
		)

	def on_cancel(self):
		doc = frappe.get_doc(
			"Booking Credit Ledger", dict(reference_doctype=self.doctype, reference_document=self.name)
		)
		doc.flags.ignore_permissions = True
		doc.cancel()

	def on_trash(self):
		self.delete_references()

	def delete_references(self):
		for doc in frappe.get_all(
			"Booking Credit Usage Reference",
			filters={"booking_credit_usage": self.name},
			pluck="name",
		):
			frappe.delete_doc("Booking Credit Usage Reference", doc)
