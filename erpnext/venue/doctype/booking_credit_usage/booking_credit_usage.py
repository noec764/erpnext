# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from erpnext.venue.doctype.booking_credit.booking_credit import (
	get_booking_credit_types_for_item,
	get_booking_credits_for_customer,
	get_converted_qty,
)
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
				"booking_credit_usage": self.name,
				"booking_credit_type": self.booking_credit_type,
			}
		)

	def before_cancel(self):
		if frappe.db.exists("Booking Credit Ledger", dict(booking_credit_usage=self.name, docstatus=1)):
			doc = frappe.get_doc("Booking Credit Ledger", dict(booking_credit_usage=self.name, docstatus=1))
			doc.flags.ignore_permissions = True
			doc.cancel()


def add_booking_credit_usage(doc, method):
	if not doc.party_type == "Customer":
		return

	if not doc.deduct_booking_credits:
		return

	if frappe.db.exists("Booking Credit Usage", {"item_booking": doc.name, "docstatus": 1}):
		return

	bct = get_booking_credit_types_for_item(doc.item, doc.uom)
	for bc in bct:
		credits = get_booking_credits_for_customer(doc.party_name, bc)
		quantity = get_converted_qty(bc, doc.item)
		if credits and credits >= quantity:
			usage = frappe.get_doc(
				{
					"doctype": "Booking Credit Usage",
					"datetime": now_datetime(),
					"customer": doc.party_name,
					"quantity": quantity,
					"user": doc.user,
					"booking_credit_type": bc,
					"item_booking": doc.name,
				}
			).insert(ignore_permissions=True)
			break

	return usage.submit()


def cancel_booking_credit_usage(doc, method):
	for bcu in frappe.get_all(
		"Booking Credit Usage",
		filters={"item_booking": doc.name},
		pluck="name",
	):
		bcu_doc = frappe.get_doc("Booking Credit Usage", bcu)
		bcu_doc.flags.ignore_permissions = True
		bcu_doc.cancel()
