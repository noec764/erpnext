# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import nowdate
from erpnext.venue.doctype.booking_credit.booking_credit import get_balance as _get_balance

@frappe.whitelist()
def get_balance(limit_start=0, limit=20, customer=None, customer_group=None, date=None, sort_order=None):
	result = []
	filters = {"customer": ("!=", "")}
	if not date:
		date = nowdate()

	if customer:
		customers = [customer]
	else:
		customers = frappe.get_list("Booking Credit Ledger", filters=filters, limit_start=limit_start, limit_page_length=limit, order_by=f"customer {sort_order}", fields=["distinct customer as name"], pluck="name")

	if customer_group and not customer:
		customers = frappe.get_list("Customer", filters={"customer_group": customer_group, "name": ("in", customers)}, pluck="name", limit_start=limit_start, limit_page_length=limit)

	for customer in customers:
		balance = _get_balance(customer, date)
		result.append({
			"customer": customer,
			"balance": balance,
			"max_count": max([x.get("balance") for x in balance]) if balance else 0
		})

	return result