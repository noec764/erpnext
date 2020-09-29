# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.venue.doctype.item_booking.item_booking import get_uom_in_minutes
from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry

class BookingCreditUsage(Document):
	def on_submit(self):
		create_ledger_entry(**{
			"customer": self.customer,
			"date": self.date,
			"credits": self.get_credits() * -1,
			"reference_doctype": self.doctype,
			"reference_document": self.name,
			"original_uom": self.uom
		})

	def on_cancel(self):
		frappe.get_doc("Booking Credit Ledger", dict(reference_doctype=self.doctype, reference_document=self.name)).cancel()

	def get_credits(self):
		return get_uom_in_minutes(self.uom) * self.quantity
