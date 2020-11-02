# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, flt, date_diff, month_diff
from erpnext.accounts.report.financial_statements import (get_period_list, get_columns)

PERIOD_MAP = {
	"Month": "Monthly",
	"Year": "Yearly"
}

def execute(filters=None):
	period_list = get_period_list(filters.from_fiscal_year, filters.to_fiscal_year,
		filters.period_start_date, filters.period_end_date, filters.filter_based_on,
		filters.periodicity, company=filters.company)

	data = get_data(filters, period_list)
	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, company=filters.company)
	columns = [x for x in columns if x.get("fieldname") != "account"]
	for column in columns:
		if column["fieldname"] == "total":
			column["label"] = _("Average")

	columns.insert(0, {
		"fieldname": "customer",
		"fieldtype": "Link",
		"options": "Customer",
		"width": 500,
		"label": _("Customer")
	})
	return columns, data, [], get_chart_data(columns, data)

def get_data(filters, period_list):
	invoices = frappe.get_all("Sales Invoice",
		filters={
			"posting_date": ("between", (filters.period_start_date, filters.period_end_date)),
			"subscription": ("is", "set"),
			"docstatus": 1
		},
		fields=["name", "subscription", "customer", "total", "posting_date", "from_date", "to_date"]
	)

	subscriptions = frappe.get_all("Subscription",
		filters={
			"status": ("!=", "Cancelled")
		},
		fields=["name", "customer", "total", "billing_interval", "billing_interval_count", "current_invoice_start", "current_invoice_end"]
	)

	filtered_invoices = []
	for subscription in subscriptions:
		filtered_invoices.extend([
			x for x in invoices if (x.from_date != subscription.current_invoice_start and x.to_date != subscription.current_invoice_end)
			and x.subscription == subscription.name
		])

	customers = list(set([x.customer for x in filtered_invoices] + [x.customer for x in subscriptions]))


	result = []
	total_row = {x.key: 0 for x in period_list if x.key != "total"}
	total_row.update({"customer": _("Total"), "total": 0})
	for customer in customers:
		customer_total = 0
		average = 0
		row = { "customer": customer, "currency": frappe.get_cached_value('Company', filters.company, "default_currency") }
		for index, period in enumerate(period_list):
			total = sum(
				[x.total for x in filtered_invoices if x.customer == customer and period.to_date >= getdate(x.posting_date) >= period.from_date]
			)

			total += get_subscription_mrr([x for x in subscriptions if x.customer == customer], period)

			customer_total += total
			total_row[period.key] += total
			total_row["total"] += total

			row.update({ period.key: total })

		row.update({ "total": flt(customer_total) / month_diff(filters.period_end_date, filters.period_start_date) })
		result.append(row)

	result.sort(key=lambda x:x["total"], reverse=True)
	result.append({})
	result.append(total_row)
	return result

def get_subscription_mrr(subscriptions, period):
	month_total = 0
	for subscription in subscriptions:
		if period.from_date < getdate(subscription.current_invoice_start):
			continue

		subscription_total = flt(subscription.total) / flt(subscription.billing_interval_count)

		if subscription.billing_interval == "Month":
			month_total = subscription_total

		elif subscription.billing_interval == "Year":
			month_total = subscription_total / 12

		elif subscription.billing_interval == "Day":
			month_total = subscription_total * date_diff(period.to_date, period.from_date)

		elif subscription.billing_interval == "Week":
			month_total = subscription_total * date_diff(period.to_date, period.from_date) / 7

	return month_total * month_diff(period.to_date, period.from_date)

def get_chart_data(columns, data):
	values = []
	for p in columns[2:]:
		if p.get("fieldname") != "total":
			values.append(data[-1].get(p.get("fieldname")))

	chart = {
		"data": {
			'labels': [d.get("label") for d in columns[2:] if d.get("fieldname") != "total"],
			'datasets': [{
				"name" : _("Monthly Recurring Revenue"),
				"values": values
			}]
		},
		"type": "line"
	}

	return chart