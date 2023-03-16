# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint

from erpnext.venue.doctype.booking_credit.booking_credit import get_balance


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart


def get_data(filters):
	result = []

	filters["docstatus"] = 1
	filters["status"] = "Active"

	customers = frappe.get_list(
		"Booking Credit", filters=filters, order_by="customer asc", pluck="customer", distinct=True
	)

	for customer in customers:
		balance = get_balance(customer)

		for index, bal in enumerate(balance):
			result.append(
				{
					"customer": customer if index == 0 else "",
					"booking_credit_type": bal,
					"balance": balance[bal],
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
			"width": 300,
		},
		{
			"fieldname": "booking_credit_type",
			"fieldtype": "Link",
			"label": _("Booking Credit Type"),
			"options": "Booking Credit Type",
			"width": 300,
		},
		{"fieldname": "balance", "fieldtype": "Int", "label": _("Balance"), "width": 200},
	]


def get_chart(data):
	data_by_booking_credit_type = defaultdict(int)

	for d in data:
		data_by_booking_credit_type[d.get("booking_credit_type")] += cint(d.get("balance"))

	chart = {
		"data": {
			"labels": [d for d in data_by_booking_credit_type],
			"datasets": [
				{
					"name": _("Balance by credit type"),
					"values": [data_by_booking_credit_type[d] for d in data_by_booking_credit_type],
				}
			],
		},
		"type": "percentage",
		"colors": [
			"#00bdff",
			"#1b3bff",
			"#8F00FF",
			"#ff0011",
			"#ff7300",
			"#ffd600",
			"#00c30e",
			"#65ff00",
			"#d200ff",
			"#FF00FF",
			"#7d7d7d",
			"#5d5d5d",
		],
	}

	return chart
