# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class BookingCreditLedger(Document):
	def on_submit(self):
		if self.reference_doctype != "Booking Credit":
			self.recalculate_fifo_balance()

	def recalculate_fifo_balance(self):
		booking_credit = frappe.qb.DocType("Booking Credit")
		query = (
			frappe.qb.from_(booking_credit)
			.select(booking_credit.name)
			.where(booking_credit.customer == self.customer)
			.where(booking_credit.booking_credit_type == self.booking_credit_type)
			.where(booking_credit.balance > 0.0)
			.where(booking_credit.status == "Active")
			.where(booking_credit.docstatus == 1)
			.orderby(booking_credit.expiration_date)
			.orderby(booking_credit.date)
		)

		if self.user:
			query = query.where((booking_credit.user == "") | (booking_credit.user == self.user))
		else:
			query = query.where(booking_credit.user == "")

		booking_credits = query.run(as_dict=True)
		if not booking_credits:
			frappe.throw(_("Please add some booking credits before making a deduction"))

		total_credits = cint(self.credits) * -1
		for bc in booking_credits:
			usable_balance = min(cint(bc.balance), total_credits)
			new_balance = cint(bc.balance) - usable_balance
			total_credits -= usable_balance
			frappe.db.set_value("Booking Credit", bc.name, "balance", new_balance)

			if new_balance == 0.0:
				doc = frappe.get_doc("Booking Credit", bc.name)
				doc.set_status()


			if not total_credits:
				break


def create_ledger_entry(**kwargs):
	entry = frappe.get_doc(
		{
			"doctype": "Booking Credit Ledger",
		}
	)
	entry.update(kwargs)
	entry.insert(ignore_permissions=True)
	entry.submit()
