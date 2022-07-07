# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_datetime, nowdate

from erpnext.venue.doctype.booking_credit.booking_credit import get_balance as _get_balance
from erpnext.venue.doctype.item_booking.item_booking import get_uom_in_minutes


@frappe.whitelist()
def get_balance(
	limit_start=0, limit=20, customer=None, customer_group=None, date=None, sort_order=None
):
	result = []
	filters = {"customer": ("!=", "")}
	if not date:
		date = nowdate()

	if customer:
		customers = [customer]
	else:
		customers = frappe.get_list(
			"Booking Credit Ledger",
			filters=filters,
			limit_start=limit_start,
			limit_page_length=limit,
			order_by=f"customer {sort_order}",
			fields=["distinct customer as name"],
			pluck="name",
		)

	if customer_group and not customer:
		customers = frappe.get_list(
			"Customer",
			filters={"customer_group": customer_group, "name": ("in", customers)},
			pluck="name",
			limit_start=limit_start,
			limit_page_length=limit,
		)

	for customer in customers:
		balance = _get_balance(customer, date)
		result.append(
			{
				"customer": customer,
				"balance": balance,
				"max_count": max([balance[x][0].get("balance") for x in balance]) if balance else 0,
			}
		)

	return result


@frappe.whitelist()
def reconcile_credits(customer, target_uom, source_item, target_item, date=None):
	if not date:
		date = nowdate()

	minute_uom = frappe.db.get_single_value("Venue Settings", "minute_uom")
	balance = _get_balance(customer, date)

	target_balance = [
		x.get("balance") for x in balance.get(target_item) if x.get("uom") == target_uom
	]
	source_balance = [
		x.get("balance") for x in balance.get(source_item) if x.get("uom") == minute_uom
	]

	if target_balance and source_balance:
		target_conversion_factor = get_uom_in_minutes(target_uom)
		target_minutes = target_balance[0] * target_conversion_factor

		convertible_qty = min(
			[
				abs(source_balance[0]),
				closestInteger(abs(source_balance[0]), target_conversion_factor),
				target_minutes,
			]
		)

		if convertible_qty > 0:
			usage = frappe.get_doc(
				{
					"doctype": "Booking Credit Usage",
					"datetime": get_datetime(date),
					"customer": customer,
					"quantity": convertible_qty * -1,
					"uom": minute_uom,
					"item": source_item,
				}
			).insert(ignore_permissions=True)
			usage.submit()

			credit = frappe.get_doc(
				{
					"doctype": "Booking Credit Usage",
					"date": get_datetime(date),
					"customer": customer,
					"quantity": convertible_qty / target_conversion_factor,
					"uom": target_uom,
					"item": target_item,
				}
			).insert(ignore_permissions=True)
			credit.submit()

			return {"indicator": "green", "message": _("Credits successfully converted")}

	return {
		"indicator": "orange",
		"message": _(
			"The amount could not be converted. Please check if the customer has enough credits and that at least one unit of credit can be converted."
		),
	}


def closestInteger(n, m):
	q = int(n / m)
	n1 = m * q
	if (n * m) > 0:
		n2 = m * (q + 1)
	else:
		n2 = m * (q - 1)

	if abs(n - n1) < abs(n - n2):
		return n1

	return n2
