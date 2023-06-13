# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe.utils import add_months, flt, format_date, get_year_start, nowdate
from frappe.utils.dashboard import cache_source

from erpnext import get_default_company
from erpnext.accounts.doctype.bank_transaction.bank_transaction import (
	get_bank_transaction_balance_on,
)


@frappe.whitelist()
@cache_source
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	filters = frappe.parse_json(filters)

	start_date = from_date or add_months(nowdate(), -3)
	if filters.get("range"):
		if filters.get("range") == "Quarterly":
			start_date = get_year_start(nowdate())
		elif filters.get("range") == "Yearly":
			start_date = get_year_start(add_months(nowdate(), -24))
		elif filters.get("range") == "Weekly":
			start_date = add_months(nowdate(), -1)

	if not filters.get("from_date"):
		filters["from_date"] = start_date

	if not filters.get("to_date"):
		filters["to_date"] = nowdate()

	if not filters.get("company"):
		filters["company"] = get_default_company()

	query_filters = {"date": ("between", [filters.get("from_date"), filters.get("to_date")])}
	if filters.get("bank_account"):
		query_filters["bank_account"] = filters.get("bank_account")

	bank_transactions = frappe.get_all(
		"Bank Transaction", filters=query_filters, fields=["date", "debit", "credit", "bank_account"]
	)

	data = defaultdict(lambda: defaultdict(float))
	dates = set()

	for transaction in bank_transactions:
		data[transaction.bank_account][transaction.date] += flt(transaction.credit) - flt(
			transaction.debit
		)
		dates.add(transaction.date)

	dates = sorted(dates)

	datasets = []
	for bank_account in data:
		dataset = {
			"name": bank_account,
			"values": [],
		}

		initial_balance = get_bank_transaction_balance_on(bank_account, dates[0])
		balance = initial_balance.get("balance")
		for label in dates:
			balance += flt(data[bank_account].get(label, 0.0))
			dataset["values"].append(balance)

		datasets.append(dataset)

	chart = {
		"labels": [format_date(d) for d in dates],
		"datasets": datasets,
		"type": "line",
		"fieldtype": "Currency",
		"colors": ["#29cd42", "#EC864B", "#449CF0"],
	}

	return chart
