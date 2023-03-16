# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from erpnext.venue.doctype.booking_credit.booking_credit import get_balance

def execute(filters=None):
	columns, data = get_columns(), get_data(filters)
	return columns, data

def get_data(filters):
	result = []

	filters["docstatus"] = 1
	filters["status"] = "Active"

	customers = frappe.get_list(
		"Booking Credit",
		filters=filters,
		order_by=f"customer asc",
		pluck="customer",
		distinct=True
	)

	for customer in customers:
		balance = get_balance(customer)

		for index, bal in enumerate(balance):
			result.append(
				{
					"customer": customer if index == 0 else "",
					"booking_credit_type": bal,
					"balance": balance[bal]
				}
			)

	return result

def get_columns():
	return [
		{
			"fieldname": "customer",
			"fieldtype": "Link",
			"label": _("Customer"),
			"options": "Customer",
			"width": 300
		},
		{
			"fieldname": "booking_credit_type",
			"fieldtype": "Link",
			"label": _("Booking Credit Type"),
			"options": "Booking Credit Type",
			"width": 300
		},
		{
			"fieldname": "balance",
			"fieldtype": "Int",
			"label": _("Balance"),
			"width": 200
		}
	]