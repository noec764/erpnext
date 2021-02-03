# Copyright (c) 2021, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt
from erpnext.controllers.taxes_and_totals import get_itemised_tax

def execute(filters=None):
	return get_data(filters)

def get_data(filters=None):
	cadrage = CadrageTVABase(filters)
	return cadrage.get_data()

class CadrageTVABase:
	def __init__(self, filters):
		self.filters = filters
		self.period = (self.filters.period_start_date, self.filters.period_end_date)
		self.data = []
		self.columns = []
		self.tax_rates = []
		tax_accounts = frappe.get_all("Account", filters={"is_group": 0, "account_type": "Tax"}, fields=["name", "account_number"])
		self.collection_accounts = [x.name for x in
			tax_accounts
			if str(x.account_number).startswith("4457")
		]

		print("Collection accounts", self.collection_accounts)

	def get_data(self):
		self.get_income_entries()
		self.get_vat_split()

		self.get_columns()

		return self.columns, self.data


	def get_income_entries(self):
		vat_entries = frappe.get_all("GL Entry",
			filters=dict(
				account=("in", self.collection_accounts),
				posting_date=("between", self.period)
			),
			fields=["voucher_type", "voucher_no"]
		)

		voucher_types = list(set([x.voucher_type for x in vat_entries]))
		by_voucher_type = {}
		for voucher_type in voucher_types:
			by_voucher_type[voucher_type] = [x.voucher_no for x in vat_entries]

		accounts = []
		for voucher_type in by_voucher_type:
			accounts.extend(frappe.get_all("GL Entry",
				filters=dict(voucher_type=voucher_type, voucher_no=("in", by_voucher_type[voucher_type])),
				pluck="account",
				distinct=1
			))

		self.get_income_expense_accounts()
		self.full_account_list = list(set([x for x in accounts if x in self.income_expense_accounts_list] + self.income_accounts_list))

		income_gl_entries = self.get_income_gl_entries(["account", "SUM(credit- debit) as total"], "account")

		grand_total = 0.0
		for gl_entry in income_gl_entries:
			grand_total += flt(gl_entry.get("total"))
			row = {
				"account": gl_entry.get("account"),
				"account_number": self.income_expense_accounts_number_dict.get(gl_entry.get("account")),
				"account_name": self.income_expense_accounts_name_dict.get(gl_entry.get("account")),
				"total": gl_entry.get("total")
			}

			self.data.append(row)

		self.data.append({
			"account": "",
			"is_total": True,
			"account_number": "",
			"account_name": _("Period Turnover"),
			"total": grand_total,
			"bold": True
		})

	def get_income_expense_accounts(self):
		income_expense_accounts = frappe.get_all("Account",
			filters=dict(account_type=("in", ("Income Account", "Expense Account"))),
			fields=["name", "account_name", "account_number", "account_type"]
		)

		self.income_expense_accounts_list = [x.name for x in income_expense_accounts]
		self.income_accounts_list = [x.name for x in income_expense_accounts if x.account_type == "Income Account"]
		self.income_expense_accounts_number_dict = {x.name: x.account_number for x in income_expense_accounts}
		self.income_expense_accounts_name_dict = {x.name: x.account_name for x in income_expense_accounts}

	def get_income_gl_entries(self, fields, group_by=None):
		return frappe.get_all("GL Entry",
			filters=dict(
				account=("in", self.full_account_list),
				posting_date=("between", self.period)
			),
			fields=fields,
			group_by=group_by
		)

	def get_vat_split(self):
		income_gl_entries = self.get_income_gl_entries(["account", "voucher_type", "voucher_no"])

		gl_by_voucher_type = defaultdict(list)
		for gl_entry in income_gl_entries:
			gl_by_voucher_type[gl_entry.voucher_type].append(gl_entry.voucher_no)

		items = []
		for voucher_type in gl_by_voucher_type:
			if voucher_type in ("Sales Invoice", "Purchase Invoice"):
				fields = ["item_code", "parent", "parenttype", "item_tax_rate", "base_net_amount"]
				fields.append("income_account as account" if voucher_type == "Sales Invoice" else "expense_account as account")

				items = frappe.get_all(f"{voucher_type} Item", 
					filters=dict(parenttype=voucher_type, parent=("in", gl_by_voucher_type[voucher_type])),
					fields=fields
				)

		gl_by_account = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
		for gl_entry in income_gl_entries:
			gl_by_account[gl_entry.account][gl_entry.voucher_type][gl_entry.voucher_no] = [x for x in items \
				if x.parenttype == gl_entry.voucher_type and x.parent == gl_entry.voucher_no and gl_entry.account == x.account]

		taxable_amount_by_account = {}
		control = 0.0
		for account in gl_by_account:
			taxable_amount_by_account[account] = defaultdict(float)
			for voucher_type in gl_by_account[account]:
				for voucher in gl_by_account[account][voucher_type]:
					if voucher_type in ("Sales Invoice", "Purchase Invoice"):
						doc = frappe.get_cached_doc(voucher_type, voucher)

						itemised_tax = get_itemised_tax(doc.taxes, True)

						calculated_base_net_amount = 0.0
						for item in gl_by_account[account][voucher_type][voucher]:
							if item.get("item_tax_rate"):
								taxes = item.get("item_tax_rate")
								for tax in frappe.parse_json(taxes):
									tax_rate = tax.get("rate")
									if tax_rate not in self.tax_rates:
										self.tax_rates.append(tax_rate)

									taxable_amount_by_account[account][tax_rate] += item.get("base_net_amount")
							else:
								taxes = itemised_tax.get(item.get("item_code"))
								for tax in taxes:
									tax_rate = itemised_tax[item.get("item_code")][tax]["tax_rate"]
									if tax_rate not in self.tax_rates:
										self.tax_rates.append(tax_rate)

									taxable_amount_by_account[account][tax_rate] += item.get("base_net_amount")

							calculated_base_net_amount += item.get("base_net_amount")

						control_value = flt(doc.base_net_total) - flt(calculated_base_net_amount)
						taxable_amount_by_account[account]["control"] = control_value
						control += control_value

					else:
						continue

		tax_total = defaultdict(float)
		for data in self.data:
			if data.get("is_total"):
				for tax_rate in self.tax_rates:
					data.update({
						str(tax_rate): tax_total.get(tax_rate, 0.0)
					})
				data.update({
					"control": control
				})
			else:
				taxable_amount = taxable_amount_by_account.get(data.get("account"))
				for tax_rate in self.tax_rates:
					tax_amount = taxable_amount.get(tax_rate, 0.0) if taxable_amount else 0.0
					tax_total[tax_rate] += flt(tax_amount)
					data.update({
						str(tax_rate): tax_amount
					})

				if taxable_amount:
					data.update({
						"control": taxable_amount.get("control")
					})

	def get_columns(self):
		self.columns = [
			{
				"fieldname": "account",
				"label": _("Account"),
				"fieldtype": "Link",
				"options": "Account",
				"hidden": 1
			},
			{
				"fieldname": "account_number",
				"label": _("Account Number"),
				"fieldtype": "Data",
				"width": 120
			},
			{
				"fieldname": "account_name",
				"label": _("Account Name"),
				"fieldtype": "Data",
				"width": 150
			},
			{
				"fieldname": "total",
				"label": _("Total"),
				"fieldtype": "Currency",
				"width": 150
			}
		]

		self.tax_rates.sort(reverse=True)
		for rate in self.tax_rates:
			self.columns.append({
					"fieldname": str(rate),
					"label": f"{str(rate)} %",
					"fieldtype": "Currency",
					"width": 180
				})

		self.columns.append({
			"fieldname": "control",
			"label": _("Control"),
			"fieldtype": "Currency",
			"width": 180
		})