# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, flt
from erpnext.venue.doctype.item_booking.item_booking import get_uom_in_minutes
from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry

class BookingCredit(Document):
	def on_submit(self):
		create_ledger_entry(**{
			"customer": self.customer,
			"date": self.date,
			"credits": self.get_credits(),
			"reference_doctype": self.doctype,
			"reference_document": self.name,
			"original_uom": self.uom
		})

	def on_cancel(self):
		frappe.get_doc("Booking Credit Ledger", dict(reference_doctype=self.doctype, reference_document=self.name)).cancel()

	def get_credits(self):
		return get_uom_in_minutes(self.uom) * self.quantity

@frappe.whitelist()
def get_balance(customer, date=None):
	booking_credits = frappe.get_all("Booking Credit Ledger",
		filters={"customer": customer, "date": ("<=", getdate(date)), "docstatus": 1},
		fields=["credits", "date", "original_uom"]
	)

	uoms = list(set([x.original_uom for x in booking_credits if x.original_uom is not None ]))

	slots = list(set([x.date for x in booking_credits]))
	slots.sort()

	balance = sum([x["credits"] for x in booking_credits if getdate(x["date"]) <= getdate(date)])
	uom_balance = {}
	for uom in uoms:
		print(uom, get_uom_in_minutes(uom))
		uom_balance[uom] = flt(balance) / flt(get_uom_in_minutes(uom))

	return {
		"balance": balance,
		"uom_balance": uom_balance
	}

def process_expired_booking_credits(date=None):
	expired_entries = frappe.get_all("Booking Credit", filters={
		"is_expired": 0,
		"expiration_date": ("<", getdate(date)),
		"docstatus": 1
	})

	for expired_entry in expired_entries:
		print(expired_entry)