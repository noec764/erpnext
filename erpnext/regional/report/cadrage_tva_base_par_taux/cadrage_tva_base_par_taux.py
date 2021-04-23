# Copyright (c) 2021, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate, add_days
from erpnext.controllers.taxes_and_totals import get_itemised_tax
from erpnext.accounts.utils import get_balance_on
from erpnext.accounts.utils import get_fiscal_year

def execute(filters=None):
	return get_data(filters)

def get_data(filters=None):
	cadrage = CadrageTVABase(filters)
	return cadrage.get_data()

class CadrageTVABase:
	def __init__(self, filters):
		self.filters = filters
		self.fiscal_year = get_fiscal_year(fiscal_year=self.filters.fiscal_year, as_dict=True)

		if not getdate(self.fiscal_year.year_start_date) <= getdate(self.filters.date) <= getdate(self.fiscal_year.year_end_date):
			frappe.throw(_("Please select a date within the selected fiscal year"))

		self.period = (self.fiscal_year.year_start_date, self.filters.date)
		self.data = []
		self.columns = []
		self.tax_rates = []
		self.precision = 2
		self.tax_accounts = frappe.get_all("Account", filters={"is_group": 0, "account_type": "Tax", "company": self.filters.company}, fields=["name", "account_number", "tax_rate"])
		self.collection_accounts = [x.name for x in
			self.tax_accounts
			if str(x.account_number).startswith("4457") or str(x.account_number).startswith("44587")
		]
		self.account_numbers = frappe.get_all("Account", pluck="account_number")
		self.total_amounts = {}

		self.total_row = {}

	def get_data(self):
		self.get_income_entries()
		self.get_vat_account_per_item()
		self.get_vat_split()
		self.get_corrections()
		self.total_turnover()
		self.get_total_collected_vat()
		self.get_vat_credits()
		self.get_vat_debits()
		self.get_vat_in_accounts_total()
		self.get_difference()
		self.control_values()

		self.get_columns()

		return self.columns, self.data

	def get_income_entries(self):
		vat_entries = frappe.get_all("GL Entry",
			filters=dict(
				account=("in", self.collection_accounts),
				posting_date=("between", self.period),
				company=self.filters.company
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
				filters=dict(voucher_type=voucher_type, voucher_no=("in", by_voucher_type[voucher_type]), company=self.filters.company),
				pluck="account",
				distinct=1
			))

		self.get_income_expense_accounts()
		self.full_account_list = list(set([x for x in accounts if x in self.income_expense_accounts_list] + self.income_accounts_list))

		income_gl_entries = self.get_income_gl_entries(["account", "SUM(credit- debit) as total"], "account")

		grand_total = 0.0
		for gl_entry in income_gl_entries:
			grand_total += flt(gl_entry.get("total"), self.precision)

			row = {
				"account": gl_entry.get("account"),
				"account_number": self.income_expense_accounts_number_dict.get(gl_entry.get("account")),
				"account_name": self.income_expense_accounts_name_dict.get(gl_entry.get("account")),
				"total": flt(gl_entry.get("total"), self.precision)
			}

			self.data.append(row)

	def get_income_expense_accounts(self):
		income_expense_accounts = frappe.get_all("Account",
			filters=dict(account_type=("in", ("Income Account", "Expense Account")), company=self.filters.company),
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
				posting_date=("between", self.period),
				company=self.filters.company,
				is_cancelled=0
			),
			fields=fields,
			group_by=group_by,
			order_by="account asc"
		)

	def get_vat_account_per_item(self):
		tax_templates = {x.parent: (x.tax_type, x.tax_rate) for x in frappe.get_all("Item Tax Template Detail",
			filters={"tax_type": ("in", self.collection_accounts)},
			fields=["parent", "tax_type", "tax_rate"]
			)
		}

		item_taxes = frappe.get_all("Item Tax", filters={"item_tax_template": ("in", tax_templates.keys())}, fields=["parent", "item_tax_template", "valid_from"])

		self.tax_per_item = defaultdict(float)

		for tax in item_taxes:
			self.tax_per_item[tax.parent] = tax_templates.get(tax.item_tax_template, ("", 0.0))

	def get_vat_split(self):
		def add_to_taxable_amount(taxable_amount_by_account, account, item, tax_rate):
			if tax_rate not in self.tax_rates:
				self.tax_rates.append(tax_rate)
			taxable_amount_by_account[account][tax_rate] += flt(item.get("base_net_amount"), self.precision)

		income_gl_entries = self.get_income_gl_entries(["account", "voucher_type", "voucher_no"])

		gl_by_voucher_type = defaultdict(list)
		for gl_entry in income_gl_entries:
			gl_by_voucher_type[gl_entry.voucher_type].append(gl_entry.voucher_no)

		items = []
		for voucher_type in gl_by_voucher_type:
			if voucher_type in ("Sales Invoice", "Purchase Invoice"):
				fields = ["item_code", "parent", "parenttype", "item_tax_rate", "base_net_amount"]
				fields.append("income_account as account" if voucher_type == "Sales Invoice" else "expense_account as account")

				items.extend(frappe.get_all(f"{voucher_type} Item",
					filters=dict(parenttype=voucher_type, parent=("in", gl_by_voucher_type[voucher_type])),
					fields=fields
				))

		gl_by_account = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
		for gl_entry in income_gl_entries:
			gl_by_account[gl_entry.account][gl_entry.voucher_type][gl_entry.voucher_no] = [x for x in items \
				if x.parenttype == gl_entry.voucher_type and x.parent == gl_entry.voucher_no and gl_entry.account == x.account]

		taxable_amount_by_account = {}
		for account in gl_by_account:
			taxable_amount_by_account[account] = defaultdict(float)
			for voucher_type in gl_by_account[account]:
				for voucher in gl_by_account[account][voucher_type]:
					if voucher_type in ("Sales Invoice", "Purchase Invoice"):
						doc = frappe.get_cached_doc(voucher_type, voucher)

						itemised_tax = get_itemised_tax(doc.taxes, True)
						for item in gl_by_account[account][voucher_type][voucher]:
							if self.tax_per_item.get(item.get("item_code")):
								tax_account, tax_rate = self.tax_per_item.get(item.get("item_code"))
								add_to_taxable_amount(taxable_amount_by_account, account, item, tax_rate)

							elif not itemised_tax:
								add_to_taxable_amount(taxable_amount_by_account, account, item, 0.0)

							elif frappe.parse_json(item.get("item_tax_rate")):
								taxes = frappe.parse_json(item.get("item_tax_rate"))
								for tax in taxes:
									tax_rate = tax.get("rate")
									add_to_taxable_amount(taxable_amount_by_account, account, item, tax_rate)

							else:
								taxes = itemised_tax.get(item.get("item_code"))
								for tax in taxes:
									if taxes[tax].get("tax_account") not in self.collection_accounts:
										continue
									tax_rate = itemised_tax[item.get("item_code")][tax]["tax_rate"]
									add_to_taxable_amount(taxable_amount_by_account, account, item, tax_rate)

					else:
						gl_entries = frappe.get_all("GL Entry",
							filters=dict(
								account=("in", self.collection_accounts + self.income_accounts_list),
								voucher_type=voucher_type,
								voucher_no=voucher,
								company=self.filters.company,
								is_cancelled=0
							),
							fields=["debit", "credit", "account"]
						)
						income_entries = {x.account: (flt(x.debit) - flt(x.credit)) * -1 for x in gl_entries if x.account in self.income_accounts_list}
						tax_entries = [x for x in gl_entries if x.account in self.collection_accounts]

						if len(tax_entries) == 1:
							tax_rates = [x for x in self.tax_accounts if x.name == tax_entries[0].account]
							if tax_rates:
								for income_entry in income_entries:
									taxable_amount_by_account[income_entry][tax_rates[0].tax_rate] += flt(income_entries[income_entry], self.precision)
						else:
							# TODO: Handle special cases
							continue

		tax_total = defaultdict(float)
		total = 0.0
		for data in self.data:
			acc = data.get("account")
			taxable_amount = taxable_amount_by_account.get(acc)
			if not taxable_amount:
				if frappe.db.get_value("Account", acc, "account_type") != "Income Account":
					self.data = [x for x in self.data if x.get("account") != acc]
					continue
				else:
					taxable_amount_by_account[acc][0.0] = data["total"]
					if 0.0 not in self.tax_rates:
						self.tax_rates.append(0.0)

			total += flt(data.get("total"), self.precision)

			for tax_rate in self.tax_rates:
				tax_amount = taxable_amount.get(tax_rate, 0.0) if taxable_amount else 0.0
				tax_total[tax_rate] += flt(tax_amount, self.precision)
				data.update({
					str(tax_rate): tax_amount
				})

		self.total_row = {
			"account": "",
			"is_total": True,
			"account_number": "",
			"account_name": _("Period Turnover"),
			"total": total,
			"bold": True
		}

		for tax_rate in self.tax_rates:
			self.total_row.update({
				str(tax_rate): tax_total.get(tax_rate, 0.0)
			})

		self.data.append(self.total_row)

	def get_corrections(self):
		account_groups = [[4181, 4198, 487], [4181, 4198, 487], [654]]
		labels = [
			_("Fiscal year start corrections"),
			_("Fiscal year end corrections"),
			_("Exceptional corrections"),
		]
		tax_accounts = frappe.get_all("Account",
			filters={"is_group": 0, "account_number": ("like", "44587%")},
			fields=["name", "account_number", "account_name", "tax_rate"]
		)


		self.data.append({})
		for index, group in enumerate(account_groups):
			if not [y for y in self.account_numbers for x in group if str(y).startswith(str(x))]:
				return

			self.data.append({
				"account": "",
				"is_total": False,
				"account_number": "",
				"account_name": labels[index],
				"total": "",
				"bold": True
			})
			for g in group:
				accounts = frappe.get_all("Account", 
					filters={"is_group": 0, "account_number": ("like", f"{g}%")},
					fields=["name", "account_number", "account_name"]
				)

				for account in accounts:
					date = self.fiscal_year.year_end_date if index == 1 else add_days(self.fiscal_year.year_start_date, -1)
					gl_entries = frappe.get_all("GL Entry",
						filters=dict(
							account=account.name,
							posting_date=("between", self.period),
							company=self.filters.company,
							is_cancelled=0
						),
						fields=f"debit, credit, voucher_type, voucher_no"
					)

					if gl_entries:
						debit = sum([flt(x.debit) for x in gl_entries])
						credit = sum([flt(x.credit) for x in gl_entries])
						self.data.append({
							"account": account.name,
							"is_total": False,
							"account_number": account.account_number,
							"account_name": account.account_name,
							"total": (flt(debit) - flt(credit)) if index == 1 else (flt(credit) - flt(debit))
						})

						tax_added = False
						for gl_entry in gl_entries:
							for tax_account in tax_accounts:
								vat_entries = frappe.get_all("GL Entry",
									filters=dict(
										account=tax_account.name,
										posting_date=("between", self.period),
										company=self.filters.company,
										is_cancelled=0
									),
									fields="sum(credit - debit) as total" if index == 1 else "sum(debit - credit) as total"
								)

								if vat_entries and vat_entries[0].get("total"):
									tax_added = True
									self.data[-1].update({
										"total": self.data[-1].get("total") - flt(vat_entries[0].get("total"), self.precision)
									})

									if tax_account.tax_rate not in self.tax_rates:
										self.tax_rates.append(tax_account.tax_rate)

									self.data[-1].update({
										str(tax_account.tax_rate): flt(vat_entries[0].get("total"), self.precision) / (tax_account.tax_rate or 1.0) * 100.0 if vat_entries[0].get("total") else (flt(debit) - flt(credit)) if index == 1 else (flt(credit) - flt(debit))
									})

						if not tax_added:
							self.data[-1].update({
								str(0.0): (flt(debit) - flt(credit)) if index == 1 else (flt(credit) - flt(debit))
							})

	def total_turnover(self):
		turnover = sum([flt(data.get("total")) for data in self.data if not data.get("bold")])
		self.data.append({
			"account": "",
			"is_total": False,
			"account_number": "",
			"account_name": _("Turnover billed during the fiscal year"),
			"total": turnover,
			"bold": True
		})

		for tax in self.tax_rates:
			total = sum([flt(data.get(str(tax))) for data in self.data if not data.get("bold")])
			self.data[-1].update({
				str(tax): total
			})

	def get_total_collected_vat(self):
		self.data.append({
			"account": "",
			"is_total": False,
			"account_number": "",
			"account_name": _("Collected VAT calculated on the turnover billed during the fiscal year"),
			"total": "",
			"bold": True
		})

		for tax in self.tax_rates:
			total = sum([flt(data.get(str(tax))) for data in self.data if not data.get("bold")])
			vat_amount = flt(total) * flt(tax) / 100.0
			self.total_amounts[tax] = [vat_amount, 0]
			self.data[-1].update({
				str(tax): vat_amount
			})

	def get_vat_credits(self):
		self.data.append({})
		self.get_vat_in_books("credit - debit", _("+ Collected tax accounting balance"))

	def get_vat_debits(self):
		references = frappe.get_all("GL Entry",
			filters=dict(
				account=("like", "4455%"),
				posting_date=("between", self.period),
				company=self.filters.company,
				is_cancelled=0,
				credit=("!=", 0)
			),
			fields=["voucher_type", "voucher_no"]
		)

		filters = dict(
			voucher_type=("in", [x.voucher_type for x in references]),
			voucher_no=("in", [x.voucher_no for x in references])
		)
		self.get_vat_in_books("debit", _("+ CA3 entries corrections"), filters)

	def get_vat_in_books(self, balance_type="credit", label=None, filters=None):
		self.data.append({
			"account": "",
			"is_total": False,
			"account_number": "",
			"account_name": label,
			"total": ""
		})

		if not filters:
			filters = {}

		for rate in self.tax_rates:
			accounts = [x.name for x in self.tax_accounts if x.tax_rate == rate and str(x.account_number).startswith("4457")]
			if accounts:
				filters.update(dict(
					account=("in", accounts),
					posting_date=("between", self.period),
					company=self.filters.company,
					is_cancelled=0
				))
				gl = frappe.get_all("GL Entry",
					filters=filters,
					fields=f"SUM({balance_type}) as total"
				)

				if gl:
					self.data[-1].update({
						str(rate): flt(gl[0].get("total"), self.precision)
					})

	def get_vat_in_accounts_total(self):
		self.data.append({
			"account": "",
			"is_total": False,
			"account_number": "",
			"account_name": _("VAT in accounts to compare"),
			"total": "",
			"bold": True
		})

		for tax in self.tax_rates:
			total = sum([flt(data.get(str(tax))) for data in self.data[-4:] if not data.get("bold")])
			self.total_amounts[tax][1] = total
			self.data[-1].update({
				str(tax): flt(total)
			})

	def get_difference(self):
		self.data.append({})
		self.data.append({
			"account": "",
			"is_total": False,
			"account_number": "",
			"account_name": _("Global difference"),
			"total": "",
			"bold": True,
			"warn_if_negative": True
		})

		for tax in self.tax_rates:
			difference = flt(self.total_amounts[tax][0], self.precision) - flt(self.total_amounts[tax][1], self.precision)
			self.data[-1].update({
				str(tax): difference
			})

	def control_values(self):
		for data in self.data:
			if data.get("total"):
				data["control"] = flt(flt(data.get("total")) - sum([flt(data.get(str(t))) for t in self.tax_rates]), self.precision)

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
				"width": 350
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