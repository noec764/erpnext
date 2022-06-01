# Copyright (c) 2022, Dokos SAS and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.query_builder import DocType, functions
from frappe.utils import (
	add_days,
	add_months,
	cint,
	flt,
	format_date,
	get_first_day,
	getdate,
	nowdate,
)

from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport
from erpnext.accounts.report.financial_statements import get_label, get_months


def execute(filters=None):
	period_list = get_period_list(filters.period_end_date, filters.periodicity)

	columns = get_columns(filters, period_list)
	data = CashFlowBudget(filters, period_list).get_data()
	return columns, data


class CashFlowBudget:
	def __init__(self, filters, period_list):
		self.filters = filters
		self.period_list = period_list
		self.result = []
		self.initial_balance = 0.0

	def get_data(self):
		self.get_initial_bank_balance()

		# Receivables / Payables
		self.get_current_receivables()
		self.get_current_payables()

		# Unreconciled payment entries

		# Expense claim payments

		# Salaries

		# Taxes

		self.get_balances()
		return self.result

	def get_current_receivables(self):
		# get all the GL entries filtered by the given filters
		args = {
			"party_type": "Customer",
			"naming_by": ["Selling Settings", "cust_master_name"],
		}

		receivables_report = ReceivablePayableReport(dict(args, **self.filters))
		receivables_report.set_defaults()
		receivables_report.get_data()
		data = receivables_report.data
		self.receivables = {"label": _("Receivables")}

		for d in data:
			for index, period in enumerate(self.period_list):
				if period.key not in self.receivables:
					self.receivables[period.key] = 0.0
				due_date = d.get("due_date") or d.get("posting_date")
				if flt(d.outstanding) > 0:  # TODO: Maybe add a filter for this condition ?
					if period.to_date >= getdate(due_date) >= period.from_date:
						self.receivables[period.key] += flt(d.outstanding)
					elif index == 0 and getdate(due_date) <= period.from_date:
						self.receivables[period.key] += flt(d.outstanding)

		self.result.append(self.receivables)

	def get_current_payables(self):
		# get all the GL entries filtered by the given filters
		args = {
			"party_type": "Supplier",
			"naming_by": ["Buying Settings", "supp_master_name"],
		}

		payables_report = ReceivablePayableReport(dict(args, **self.filters))
		payables_report.set_defaults()
		payables_report.get_data()
		data = payables_report.data
		self.payables = {"label": _("Payables")}

		for d in data:
			for index, period in enumerate(self.period_list):
				if period.key not in self.payables:
					self.payables[period.key] = 0.0
				due_date = d.get("due_date") or d.get("posting_date")
				if flt(d.outstanding) > 0:  # TODO: Maybe add a filter for this condition ?
					if period.to_date >= getdate(due_date) >= period.from_date:
						self.payables[period.key] -= flt(d.outstanding)
					elif index == 0 and getdate(due_date) <= period.from_date:
						self.payables[period.key] -= flt(d.outstanding)

		self.result.append(self.payables)

	def get_initial_bank_balance(self):
		bt = DocType("Bank Transaction")
		balance = (
			frappe.qb.from_(bt)
			.select(
				(functions.Sum(bt.credit) - functions.Sum(bt.debit)).as_("balance"),
			)
			.where(bt.date <= nowdate())
			.run(as_dict=True)
		)
		if not balance[0] and not balance[0].balance:
			frappe.throw(_("This report cannot be generated without bank transactions"))

		self.initial_balance = balance[0].balance
		self.result.append(
			{"label": _("Initial Balance"), self.period_list[0].key: self.initial_balance}
		)
		self.result.append({})

	def get_balances(self):
		balance_row = {"label": _("Balance")}

		for row in self.result:
			for period in self.period_list:
				if period.key not in balance_row:
					balance_row[period.key] = 0.0
				balance_row[period.key] += flt(row.get(period.key))

		self.result.append({})
		self.result.append(balance_row)


def get_period_list(period_end_date, periodicity):
	"""Get a list of dict {"from_date": from_date, "to_date": to_date, "key": key, "label": label}
	Periodicity can be (Yearly, Quarterly, Monthly)"""
	year_start_date = getdate(nowdate())
	year_end_date = getdate(period_end_date)

	months_to_add = {"Yearly": 12, "Half-Yearly": 6, "Quarterly": 3, "Monthly": 1}[periodicity]

	period_list = []

	start_date = year_start_date
	months = get_months(year_start_date, year_end_date)

	for i in range(cint(math.ceil(months / months_to_add))):
		period = frappe._dict({"from_date": start_date})

		if i == 0:
			to_date = add_months(get_first_day(start_date), months_to_add)
		else:
			to_date = add_months(start_date, months_to_add)

		start_date = to_date

		# Subtract one day from to_date, as it may be first day in next fiscal year or month
		to_date = add_days(to_date, -1)

		if to_date <= year_end_date:
			# the normal case
			period.to_date = to_date
		else:
			# if a fiscal year ends before a 12 month period
			period.to_date = year_end_date

		period_list.append(period)

		if period.to_date == year_end_date:
			break

	# common processing
	for opts in period_list:
		key = opts["to_date"].strftime("%b_%Y").lower()
		if periodicity == "Monthly":
			label = format_date(opts["to_date"], "MMM YYYY")
		else:
			label = get_label(periodicity, opts["from_date"], opts["to_date"])

		opts.update(
			{
				"key": key.replace(" ", "_").replace("-", "_"),
				"label": label,
				"year_start_date": year_start_date,
				"year_end_date": year_end_date,
			}
		)

	return period_list


def get_columns(filters, period_list):
	columns = [{"fieldname": "label", "fieldtype": "Data", "width": 400}]
	currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	for period in period_list:
		columns.append(
			{
				"fieldname": period.key,
				"fieldtype": "Currency",
				"label": period.label,
				"width": 300,
				"options": currency,
			}
		)

	return columns
