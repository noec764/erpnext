# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class BookingCreditLedger(Document):
	def on_submit(self):
		self.calculate_fifo_balance()

	def calculate_fifo_balance(self):
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
			remaining = self.set_fifo_balance(bc, total_credits)
			if not remaining:
				break

	def set_fifo_balance(self, booking_credit, total_credits):
		usable_balance = min(cint(booking_credit.balance), total_credits)

		doc = frappe.get_doc("Booking Credit", booking_credit.name)
		doc.append(
			"booking_credit_ledger_allocation",
			{"booking_credit_ledger": self.name, "allocation": usable_balance},
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_links = True
		doc.flags.ignore_mandatory = True
		doc.save()

		total_credits -= usable_balance
		return total_credits


def create_ledger_entry(**kwargs):
	entry = frappe.get_doc(
		{
			"doctype": "Booking Credit Ledger",
		}
	)
	entry.update(kwargs)
	entry.insert(ignore_permissions=True)
	entry.submit()
