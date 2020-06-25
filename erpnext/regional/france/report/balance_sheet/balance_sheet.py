# Copyright (c) 2020, Dokos SAS and Contributors
# License: See license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint
from erpnext.accounts.report.financial_statements import (get_period_list, get_columns, get_data)
from erpnext.accounts.report.balance_sheet.balance_sheet import get_provisional_profit_loss, check_opening_balance, get_report_summary, get_chart_data

def execute(filters=None):
	period_list = get_period_list(filters.from_fiscal_year, filters.to_fiscal_year,
		filters.period_start_date, filters.period_end_date, filters.filter_based_on,
		filters.periodicity, company=filters.company)

	currency = filters.presentation_currency or frappe.get_cached_value('Company',  filters.company,  "default_currency")

	asset = get_data(filters.company, "Asset", "Debit", period_list,
		only_current_fiscal_year=False, filters=filters,
		accumulated_values=filters.accumulated_values)

	liability = get_data(filters.company, "Liability", "Credit", period_list,
		only_current_fiscal_year=False, filters=filters,
		accumulated_values=filters.accumulated_values)

	equity = get_data(filters.company, "Equity", "Credit", period_list,
		only_current_fiscal_year=False, filters=filters,
		accumulated_values=filters.accumulated_values)

	provisional_profit_loss, total_credit = get_provisional_profit_loss(asset, liability, equity,
		period_list, filters.company, currency)

	message, opening_balance = check_opening_balance(asset, liability, equity)

	data = []
	data.extend(asset or [])
	data.extend(equity or [])
	data.extend(liability or [])
	if opening_balance and round(opening_balance,2) !=0:
		unclosed ={
			"account_name": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
			"account": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
			"warn_if_negative": True,
			"currency": currency
		}
		for period in period_list:
			unclosed[period.key] = opening_balance
			if provisional_profit_loss:
				provisional_profit_loss[period.key] = provisional_profit_loss[period.key] - opening_balance

		unclosed["total"]=opening_balance
		data.append(unclosed)

	if provisional_profit_loss:
		data.append(provisional_profit_loss)
	if total_credit:
		data.append(total_credit)

	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, company=filters.company)

	chart = get_chart_data(filters, columns, asset, liability, equity)

	report_summary = get_report_summary(period_list, asset, liability, equity, provisional_profit_loss,
		total_credit, currency, filters)

	return columns, data, message, chart, report_summary