# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, flt, now_datetime, add_days
from erpnext.venue.doctype.item_booking.item_booking import get_uom_in_minutes
from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry
from erpnext.controllers.website_list_for_contact import get_customers_suppliers

class BookingCredit(Document):
	def on_submit(self):
		create_ledger_entry(**{
			"user": self.user,
			"customer": self.customer,
			"date": self.date,
			"credits": self.quantity,
			"reference_doctype": self.doctype,
			"reference_document": self.name,
			"uom": self.uom
		})

	def on_cancel(self):
		frappe.get_doc("Booking Credit Ledger", dict(reference_doctype=self.doctype, reference_document=self.name)).cancel()

@frappe.whitelist()
def get_balance(customer, date=None):
	booking_credits = frappe.get_all("Booking Credit Ledger",
		filters={"customer": customer, "date": ("<", add_days(getdate(date), 1)), "docstatus": 1},
		fields=["credits", "date", "uom"],
		order_by="date DESC"
	)

	uoms = list(set([x.uom for x in booking_credits if x.uom is not None]))

	balance = []
	for uom in uoms:
		row = {"uom": uom}

		fifo_date = now_datetime()
		for credit in [x for x in booking_credits if x.uom == uom]:
			bal = sum([x["credits"] for x in booking_credits if x.uom == uom and getdate(x["date"]) <= getdate(credit["date"])])
			if bal <= 0:
				break
			else:
				fifo_date = credit.date

		row["date"] = fifo_date
		row["balance"] = sum([x["credits"] for x in booking_credits if getdate(x["date"]) <= getdate(date) and x["uom"] == uom])
		balance.append(row)

	return balance

def process_expired_booking_credits(date=None):
	expired_entries = frappe.get_all("Booking Credit", filters={
		"is_expired": 0,
		"expiration_date": ("<", getdate(date)),
		"docstatus": 1
	}, fields=["name", "quantity", "uom", "customer"])

	for expired_entry in expired_entries:
		balance = sum(frappe.get_all("Booking Credit Ledger",
			filters={
				"customer": expired_entry.customer,
				"date": ("<", add_days(get_datetime(date), 1)),
				"docstatus": 1,
				"uom": expired_entry.uom
			},
			fields=["credits"],
			order_by="date DESC",
			pluck="credits"
		))

		credits_left = sum(frappe.get_all("Booking Credit", 
			filters={
				"customer": expired_entry.customer,
				"is_expired": 0,
				"date": (">=", expired_entry.date),
				"uom": expired_entry.uom,
				"docstatus": 1
			},
			fields=["quantity"],
			pluck="quantity"
		))

		if balance > credits_left:
			create_ledger_entry(**{
				"user": expired_entry.user,
				"customer": expired_entry.customer,
				"date": get_datetime(expired_entry.expiration_date),
				"credits": balance - credits_left,
				"reference_doctype": expired_entry.doctype,
				"reference_document": expired_entry.name,
				"uom": expired_entry.uom
			})

		frappe.db.set_value("Booking Credit", expired_entry.name, "is_expired", 1)


@frappe.whitelist()
def get_customer(user):
	customers, suppliers = get_customers_suppliers("Customer", user)
	return customers[0] if customers else ""