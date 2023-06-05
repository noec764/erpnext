# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _


def execute(filters=None):
	if not filters:
		filters = {}

	if not filters.get("date"):
		frappe.throw(_("Please select date"))

	columns = get_columns()

	query_filters = {"is_company": 0}
	if filters.get("shareholder"):
		query_filters = {"name": filters.get("shareholder")}

	data = []

	for shareholder in frappe.get_all("Shareholder", filters=query_filters, pluck="name"):
		share_type, no_of_shares, rate, amount = 1, 2, 3, 4
		all_shares = get_all_shares(shareholder)
		for share_entry in all_shares:
			row = False
			for datum in data:
				if datum[share_type] == share_entry.share_type:
					datum[no_of_shares] += share_entry.no_of_shares
					datum[amount] += share_entry.amount
					if datum[no_of_shares] == 0:
						datum[rate] = 0
					else:
						datum[rate] = datum[amount] / datum[no_of_shares]
					row = True
					break
			# new entry
			if not row:
				row = [
					shareholder,
					share_entry.share_type,
					share_entry.no_of_shares,
					share_entry.rate,
					share_entry.amount,
				]

				data.append(row)

	return columns, data


def get_columns():
	columns = [
		_("Shareholder") + ":Link/Shareholder:180",
		_("Share Type") + "::150",
		_("No of Shares") + ":Float:150",
		_("Average Rate") + ":Currency:150",
		_("Amount") + ":Currency:150",
	]
	return columns


def get_all_shares(shareholder):
	return frappe.get_doc("Shareholder", shareholder).share_balance
