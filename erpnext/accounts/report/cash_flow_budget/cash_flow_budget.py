# Copyright (c) 2022, Dokos SAS and contributors
# For license information, please see license.txt

import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.query_builder import DocType, functions
from frappe.utils import (
	add_days,
	add_months,
	add_to_date,
	cint,
	date_diff,
	flt,
	format_date,
	get_first_day,
	getdate,
	nowdate,
)

from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport
from erpnext.accounts.report.financial_statements import get_label, get_months


def execute(filters=None):
	period_list = get_period_list(filters.period_end_date, "Monthly")

	columns = get_columns(filters, period_list)
	report = CashFlowBudget(filters, period_list)
	data = report.get_data()
	chart = report.chart
	return columns, data, None, chart


class CashFlowBudget:
	def __init__(self, filters, period_list):
		self.filters = filters
		self.period_list = period_list
		self.result = []
		self.initial_balance = 0.0

	def get_data(self):
		self.get_initial_bank_balance()

		# Receivables
		self.get_current_receivables()

		# Subscriptions
		self.get_subscription_amounts()

		# Auto Repeat
		self.get_revenue_from_auto_repeat()

		self.result.append({})

		# Payables
		self.get_current_payables()

		# Auto Repeat
		self.get_expenses_from_auto_repeat()

		# Expense claim payments
		self.get_unpaid_expense_claims()

		# Unreconciled payment entries
		self.result.append({})
		self.get_unreconciled_payment_entries()

		# Salaries

		self.get_balances()
		self.get_chart_data()

		return self.result

	def get_current_receivables(self):
		# get all the GL entries filtered by the given filters
		args = {
			"party_type": "Customer",
			"naming_by": ["Selling Settings", "cust_master_name"],
			"show_future_payments": 1,
		}

		self.receivables_report = ReceivablePayableReport(dict(args, **self.filters))
		self.receivables_report.set_defaults()
		self.receivables_report.get_data()
		data = self.receivables_report.data
		self.receivables = {"label": _("Receivables")}

		self.voucher_dict = defaultdict(str)
		for ple in self.receivables_report.ple_entries:
			self.voucher_dict[ple.voucher_no] = ple.due_date

		for d in data:
			for index, period in enumerate(self.period_list):
				if period.key not in self.receivables:
					self.receivables[period.key] = 0.0
				due_date = add_days(
					d.get("due_date") or d.get("posting_date"),
					self.get_average_payment_age(d.party, self.receivables_report),
				)
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
			"show_future_payments": 1,
		}

		self.payables_report = ReceivablePayableReport(dict(args, **self.filters))
		self.payables_report.set_defaults()
		self.payables_report.get_data()
		data = self.payables_report.data
		self.payables = {"label": _("Payables")}

		if not self.voucher_dict:
			self.voucher_dict = defaultdict(str)
			for ple in self.payables_report.ple_entries:
				self.voucher_dict[ple.voucher_no] = ple.due_date

		for d in data:
			for index, period in enumerate(self.period_list):
				if period.key not in self.payables:
					self.payables[period.key] = 0.0
				due_date = add_days(
					d.get("due_date") or d.get("posting_date"),
					self.get_average_payment_age(d.party, self.payables_report),
				)
				if flt(d.outstanding) > 0:  # TODO: Maybe add a filter for this condition ?
					if period.to_date >= getdate(due_date) >= period.from_date:
						self.payables[period.key] -= flt(d.outstanding)
					elif index == 0 and getdate(due_date) <= period.from_date:
						self.payables[period.key] -= flt(d.outstanding)

		self.result.append(self.payables)

	def get_average_payment_age(self, party, report):
		ages = []
		for ple in report.ple_entries:
			if ple.voucher_type in ("Payment Entry", "Journal Entry") and ple.party == party:
				ages.append(date_diff(ple.posting_date, self.voucher_dict.get(ple.against_voucher_no)))

		return sum(ages) / len(ages) if ages else 0

	def get_subscription_amounts(self):
		# TODO: Improve accuracy while taking performance into account
		subscriptions = frappe.get_all(
			"Subscription",
			filters={"status": ("!=", "Cancelled")},
			fields=[
				"name",
				"customer",
				"total",
				"billing_interval",
				"billing_interval_count",
				"current_invoice_start",
				"current_invoice_end",
			],
		)

		self.subscriptions = {"label": _("Subscriptions")}
		for subscription in subscriptions:
			next_invoicing_date = add_days(subscription.current_invoice_end, 1)
			for period in self.period_list:
				if period.key not in self.subscriptions:
					self.subscriptions[period.key] = 0.0

				invoicing_date_with_delay = add_days(
					next_invoicing_date,
					self.get_average_payment_age(subscription.customer, self.receivables_report),
				)
				if getdate(period.to_date) >= invoicing_date_with_delay >= getdate(period.from_date):
					self.subscriptions[period.key] += flt(subscription.total)

				if getdate(period.to_date) >= next_invoicing_date >= getdate(period.from_date):
					next_invoicing_date = add_to_date(
						next_invoicing_date,
						**self.get_billing_cycle_data(
							subscription.billing_interval,
							subscription.billing_interval_count,
						)
					)

		if len(self.subscriptions.keys()) > 1:
			self.result.append(self.subscriptions)

	def get_billing_cycle_data(self, interval, interval_count):
		data = {}
		# if interval not in ["Day", "Daily", "Week", "Weekly"]:
		# 	data["days"] = -1
		if interval in ("Day", "Daily"):
			data["days"] = interval_count - 1
		elif interval in ("Month", "Monthly"):
			data["months"] = interval_count
		elif interval == "Quarterly":
			data["months"] = interval_count * 3
		elif interval == "Half-yearly":
			data["months"] = interval_count * 6
		elif interval in ("Year", "Yearly"):
			data["years"] = interval_count
		elif interval in ("Week", "Weekly"):
			data["days"] = interval_count * 7 - 1

		return data


	def get_revenue_from_auto_repeat(self):
		self.get_data_from_auto_repeat("Sales Invoice")

	def get_expenses_from_auto_repeat(self):
		self.get_data_from_auto_repeat("Purchase Invoice")

	def get_data_from_auto_repeat(self, reference_doctype):
		# TODO: Improve accuracy while taking performance into account
		auto_repeat = frappe.get_all("Auto Repeat",
			filters={"reference_doctype": reference_doctype, "disabled": 0},
			fields=["reference_document", "next_schedule_date", "frequency", "repeat_on_day", "repeat_on_last_day"]
		)

		auto_repeat_data = {"label": _("Auto Repeat")}
		for doc in auto_repeat:
			invoice = frappe.db.get_value(reference_doctype, doc.reference_document,
				["supplier as party" if reference_doctype == "Purchase Invoice" else "customer as party", "base_grand_total"], as_dict=True)
			next_schedule_date = doc.next_schedule_date
			for period in self.period_list:
				if period.key not in auto_repeat_data:
					auto_repeat_data[period.key] = 0.0

				invoicing_date_with_delay = add_days(
					next_schedule_date,
					self.get_average_payment_age(invoice.party, self.payables_report if reference_doctype == "Purchase Invoice" else self.receivables_report),
				)

				if getdate(period.to_date) >= getdate(invoicing_date_with_delay) >= getdate(period.from_date):
					auto_repeat_data[period.key] += flt(invoice.base_grand_total) * -1

				if getdate(period.to_date) >= getdate(next_schedule_date) >= getdate(period.from_date):
					next_schedule_date = add_to_date(
						next_schedule_date,
						**self.get_billing_cycle_data(
							doc.frequency,
							1,
						)
					)

		if len(auto_repeat_data.keys()) > 1:
			self.result.append(auto_repeat_data)

	def get_unpaid_expense_claims(self):
		ec = DocType("Expense Claim")
		gle = DocType("GL Entry")
		unpaid_exp_claims = (
			frappe.qb.from_(gle)
			.from_(ec)
			.select(
				(functions.Sum(gle.credit) - functions.Sum(gle.debit)).as_("outstanding_amt"),
				ec.posting_date
			)
			.where(
				(gle.party.isnotnull())
				&(gle.against_voucher_type == "Expense Claim")
				&(gle.against_voucher == ec.name)
				&(ec.docstatus == 1)
				&(ec.is_paid == 0)
			)
			.groupby(ec.name)
			.having(functions.Sum(gle.credit) - functions.Sum(gle.debit) > 0)
			.run(as_dict=True)
		)

		self.expense_claims = {"label": _("Expense Claims")}
		for expense_claim in unpaid_exp_claims:
			for period in self.period_list:
				if period.key not in self.expense_claims:
					self.expense_claims[period.key] = 0.0

				if getdate(expense_claim.posting_date) < getdate(period.from_date) or getdate(period.to_date) >= getdate(expense_claim.posting_date) >= getdate(period.from_date):
					self.expense_claims[period.key] += flt(expense_claim.outstanding_amt) * -1
					break

		if len(self.expense_claims.keys()) > 1:
			self.result.append(self.expense_claims)

	def get_unreconciled_payment_entries(self):
		# TODO: Take into account a delay by payment method
		payments = frappe.get_all("Payment Entry",
			filters={"unreconciled_amount": (">=", 0.0), "docstatus": 1},
			fields=["posting_date", "unreconciled_amount", "payment_type"]
		)

		self.unreconciled_payments = {"label": _("Unreconciled Payments")}
		for payment in payments:
			for period in self.period_list:
				if period.key not in self.unreconciled_payments:
					self.unreconciled_payments[period.key] = 0.0

				if getdate(payment.posting_date) < getdate(period.from_date) or getdate(period.to_date) >= getdate(payment.posting_date) >= getdate(period.from_date):
					self.unreconciled_payments[period.key] += flt(payment.unreconciled_amount) * (-1 if payment.payment_type == "Pay" else 1)
					break

		if len(self.unreconciled_payments.keys()) > 1:
			self.result.append(self.unreconciled_payments)

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

		for index, period in enumerate(self.period_list):
			if index > 0:
				balance_row[period.key] += balance_row.get(self.period_list[index - 1].key)

		self.result.append({})
		self.result.append(balance_row)

	def get_chart_data(self):
		data = {x: self.result[-1][x] for x in self.result[-1] if x != "label"}
		self.chart = {
			"data": {
				"labels": [p.get("label") for p in self.period_list for x in data.keys() if x == p.key],
				"datasets": [{"name": "", "values": [flt(x) for x in data.values()]}],
			},
			"type": "line",
			"colors": ["light-green"],
			"lineOptions": {"regionFill": 1},
			"fieldtype": "Currency",
		}


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
				"width": 250,
				"options": currency,
			}
		)

	return columns
