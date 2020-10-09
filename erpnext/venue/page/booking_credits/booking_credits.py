# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import nowdate
from erpnext.venue.doctype.booking_credit.booking_credit import get_balance as _get_balance

@frappe.whitelist()
def get_balance(limit=20, customer=None, customer_group=None, date=None):
	result = []
	filters = {}
	if not date:
		date = nowdate()

	if customer:
		customers = (customer)
	else:
		customers = list(set(frappe.get_list("Booking Credit Ledger", filters=filters, limit=limit, fields=["customer as name"], pluck="name")))

	if customer_group and not customer:
		customers = frappe.get_list("Customer", filters={"customer_group": customer_group, "name": ("in", customers)}, pluck="name")

	for customer in customers:
		balance = _get_balance(customer, date)
		result.append({
			"customer": customer,
			"balance": balance,
			"max_count": max([x.get("balance") for x in balance]) if balance else 0
		})

	return result