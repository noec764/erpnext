# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry
from erpnext.venue.utils import get_customer
from erpnext.venue.doctype.booking_credit.booking_credit import get_booking_credit_types_for_item, get_converted_qty


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
				"booking_credit_type": self.booking_credit_type
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


def add_booking_credit_usage(doc, method):
	if not doc.party_type == "Customer":
		return

	if not doc.deduct_booking_credits:
		return

	if frappe.db.exists("Booking Credit Usage", {"item_booking": doc.name, "docstatus": 1}):
		return

	bct = get_booking_credit_types_for_item(doc.item, doc.uom)
	if bct:
		usage = frappe.get_doc(
			{
				"doctype": "Booking Credit Usage",
				"datetime": now_datetime(),
				"customer": doc.party_name,
				"quantity": get_converted_qty(bct[0], doc.item),
				"user": doc.user,
				"booking_credit_type": bct[0],
				"item_booking": doc.name
			}
		).insert(ignore_permissions=True)

	return usage.submit()


def cancel_booking_credit_usage(doc, method):
	doc_before_save = doc.get_doc_before_save()
	if doc_before_save:
		for field in ("status", "starts_on", "ends_on", "party_name"):
			if doc_before_save.get(field) != doc.get(field):
				for bcu in frappe.get_all(
					"Booking Credit Usage",
					filters={"item_booking", doc.name},
					pluck="name",
				):
					bcu_doc = frappe.get_doc("Booking Credit Usage", bcu)
					bcu_doc.flags.ignore_permissions = True
					bcu_doc.cancel()