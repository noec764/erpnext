# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import cint


class BookingCreditLedger(Document):
	def on_submit(self):
		if self.reference_doctype != "Booking Credit":
			self.recalculate_fifo_balance()

	def recalculate_fifo_balance(self):
		filters={
			"customer": self.customer,
			"booking_credit_type": self.booking_credit_type,
			"balance": (">", 0.0),
			"status": "Active",
			"docstatus": 1
		}

		if self.user:
			filters["user"] = self.user

		total_credits = cint(self.credits) * -1
		for bc in frappe.get_all(
			"Booking Credit",
			filters=filters,
			fields=["name", "balance"],
			order_by="expiration_date ASC, date ASC"
		):
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
