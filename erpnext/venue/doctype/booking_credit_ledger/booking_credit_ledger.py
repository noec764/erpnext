# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document


class BookingCreditLedger(Document):
	pass


def create_ledger_entry(**kwargs):
	entry = frappe.get_doc(
		{
			"doctype": "Booking Credit Ledger",
		}
	)
	entry.update(kwargs)
	entry.insert(ignore_permissions=True)
	entry.submit()
