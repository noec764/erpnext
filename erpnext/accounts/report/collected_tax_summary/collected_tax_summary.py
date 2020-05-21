# Copyright (c) 2013, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from collections import defaultdict
from frappe.utils import flt
from erpnext.controllers.taxes_and_totals import get_itemised_tax_breakup_data
from erpnext.accounts.report.financial_statements import get_accounts

def execute(filters=None):
	return get_data(filters)

def get_data(filters=None):
	summary = CollectedTaxSummary(filters)
	return summary.get_data()


class CollectedTaxSummary:
	def __init__(self, filters):
		self.filters = filters
		self.data = []
		self.columns = []
		self.tax_rates_by_account = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
		self.tax_accounts = frappe.get_all("Account", filters={"is_group": 0, "account_type": "Tax"}, fields=["name", "tax_rate"])
		self.sales_invoices = frappe.get_all("Sales Invoice",
			filters={
				"company": self.filters.company,
				"posting_date": ("between", (self.filters.period_start_date, self.filters.period_end_date)),
				"docstatus": 1
			}
		)

	def get_data(self):
		self.get_data_from_sales_invoices()
		self.get_data_from_journals()


		return self.columns, self.data

	def get_data_from_sales_invoices(self):
		for sales_invoice in self.sales_invoices:
			doc = frappe.get_doc("Sales Invoice", sales_invoice.name)
			itemised_tax, itemised_taxable_amount = get_itemised_tax_breakup_data(doc)

			processed_items = []
			for item in doc.items:
				if item.item_code in processed_items:
					continue
				else:
					processed_items.append(item.item_code)

				total_amount = 0
				if itemised_tax:
					for tax in itemised_tax.get(item.item_code):
						tax_rate = flt(itemised_tax[item.item_code][tax].get("tax_rate"))
						tax_amount = flt(itemised_tax[item.item_code][tax].get("tax_amount"))
						amount = ((tax_amount * 100) / tax_rate) if tax_rate != 0 else 0
						total_amount += flt(amount)
						self.tax_rates_by_account[item.income_account][tax_rate]["tax_amount"] += flt(amount)

				if not total_amount:
					self.tax_rates_by_account[item.income_account][0.0]["tax_amount"] += itemised_taxable_amount.get(item.item_code)

		self.get_data_by_account()

	def get_data_by_account(self):
		headers = ["account_number", "account_name", "total"]
		tax_rates = {}
		grand_total = 0
		grand_control = 0
		for account in self.tax_rates_by_account:
			total = self.get_account_balance(account, "Sales Invoice")
			account_name, account_number = frappe.db.get_value("Account", account, ["account_name", "account_number"])

			for tax_total in self.tax_rates_by_account[account]:
				if not tax_total in tax_rates:
					tax_rates.update({tax_total: 0})

			line = {
				"account_number": account_number,
				"account_name": account_name,
				"total": total,
			}

			grand_total += total
			control = 0
			for tax_rate in tax_rates:
				headers.append(tax_rate)
				tax_rate_amount = self.tax_rates_by_account[account].get(tax_rate, {}).get("tax_amount")
				control += flt(tax_rate_amount)
				tax_rates[tax_rate] += flt(tax_rate_amount)
				line.update({tax_rate: tax_rate_amount})

			grand_control += control
			line.update({"control": flt(control) - flt(total)})
			headers.append("control")

			self.data.append(line)

		total_line = {
			headers[1]: _("Net sales from sales invoices during the period"),
			headers[2]: grand_total
		}

		for header in headers[3:-1]:
			total_line.update({
				header: tax_rates.get(header)
			})

		total_line.update({ headers[-1]: flt(grand_control) - flt(grand_total) })

		self.data.append(total_line)

		self.get_columns(sorted(tax_rates, reverse=True))

	def get_data_from_journals(self):
		self.data.append([])
		grand_total = 0
		tax_rates_total = {}
		for account in self.tax_accounts:
			tax_rates = {}
			if str(account.tax_rate) not in tax_rates:
				tax_rates.update({str(account.tax_rate): 0.0})

			if str(account.tax_rate) not in tax_rates_total:
				tax_rates_total.update({str(account.tax_rate): 0.0})

			gl_entries = frappe.get_all("GL Entry", filters={
				"account": account.name,
				"is_cancelled": 0,
				"docstatus": 1,
				"posting_date": ("between", (self.filters.period_start_date, self.filters.period_end_date)),
				"company": self.filters.company,
				"voucher_type": ("in", ("Journal Entry"))
			}, fields=["sum(credit) - sum(debit) as balance", "name"])

			if gl_entries and gl_entries[0].balance:
				balance = gl_entries[0].balance or 0
				grand_total += balance
				tax_rates[str(account.tax_rate)] += balance
				tax_rates_total[str(account.tax_rate)] += balance

				account_name, account_number = frappe.db.get_value("Account", account.name, ["account_name", "account_number"])
				line = {
					"account_number": account_number,
					"account_name": account_name,
					"total": balance,
				}

				for tax_rate in tax_rates:
					if str(tax_rate) not in [x.get("fieldname") for x in self.columns]:
						self.columns.insert(-1, {
							"fieldname": str(tax_rate),
							"label": _(str(tax_rate)),
							"fieldtype": "Currency",
							"width": 140
						})

					line.update({
						tax_rate: tax_rates[tax_rate]
					})

				self.data.append(line)


		headers = [x.get("fieldname") for x in self.columns]
		total_line = {
			headers[1]: _("Taxes registered in journal entries"),
			headers[2]: grand_total
		}

		for header in headers[3:-1]:
			total_line.update({
				header: tax_rates_total.get(str(header))
			})

		self.data.append(total_line)


	def get_account_balance(self, account, voucher_type):
		balance = frappe.get_all("GL Entry", filters={
			"account": account,
			"is_cancelled": 0,
			"docstatus": 1,
			"posting_date": ("between", (self.filters.period_start_date, self.filters.period_end_date)),
			"company": self.filters.company,
			"voucher_type": voucher_type
		}, fields=["sum(credit) - sum(debit) as balance"])
		return balance[0].balance if balance else 0

	def get_columns(self, tax_accounts):
		self.columns = [
			{
				"fieldname": "account_number",
				"label": _("Account Number"),
				"width": 180
			},
			{
				"fieldname": "account_name",
				"label": _("Account Name"),
				"width": 300
			},
			{
				"fieldname": "total",
				"label": _("Total from General Ledger"),
				"fieldtype": "Currency",
				"width": 180
			}
		]

		for account in tax_accounts:
			self.columns.append({
					"fieldname": str(account),
					"label": _(str(account)),
					"fieldtype": "Currency",
					"width": 140
				})

		self.columns.append({
				"fieldname": "control",
				"label": _("Control"),
				"fieldtype": "Currency",
				"width": 100
			})