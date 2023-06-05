# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _


def execute(filters=None):
	if not filters:
		filters = {}

	if not filters.get("date"):
		frappe.throw(_("Please select date"))

	columns = get_columns()

	date = filters.get("date")

	data = []

	transfers = get_all_transfers(date, filters.get("shareholder"))
	for transfer in transfers:
		if transfer.transfer_type == "Transfer":
			if transfer.from_shareholder == filters.get("shareholder"):
				transfer.transfer_type += " to {}".format(transfer.to_shareholder)
			else:
				transfer.transfer_type += " from {}".format(transfer.from_shareholder)
		row = [
			filters.get("shareholder") or transfer.from_shareholder or transfer.to_shareholder,
			transfer.date,
			transfer.transfer_type,
			transfer.share_type,
			transfer.no_of_shares,
			transfer.rate,
			transfer.amount,
			transfer.company,
			transfer.name,
		]

		data.append(row)

	return columns, data


def get_columns():
	columns = [
		_("Shareholder") + ":Link/Shareholder:180",
		_("Date") + ":Date:100",
		_("Transfer Type") + "::140",
		_("Share Type") + "::150",
		_("No of Shares") + ":Float:120",
		_("Rate") + ":Currency:100",
		_("Amount") + ":Currency:150",
		_("Company") + "::150",
		_("Share Transfer") + ":Link/Share Transfer:180",
	]
	return columns


def get_all_transfers(date, shareholder=None):

	share_transfer = frappe.qb.DocType("Share Transfer")

	query = (
		frappe.qb.from_(share_transfer)
		.select("*")
		.where(share_transfer.date <= date)
		.where(share_transfer.docstatus == 1)
	)

	if shareholder:
		query.where(
			(share_transfer.from_shareholder == shareholder)
			| (share_transfer.to_shareholder == shareholder)
		)

	return query.run(as_dict=True)
