# Copyright (c) 2021, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	return get_data(filters)

def get_data(filters=None):
	summary = TaxSummary(filters)
	return summary.get_data()


class TaxSummary:
	def __init__(self, filters):
		self.filters = filters
		self.data = []
		self.columns = []
		self.tax_rates = []
		self.tax_accounts = frappe.get_all("Account", filters={"is_group": 0, "account_type": "Tax"}, fields=["name", "tax_rate"])
		self.parents = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

	def get_data(self):
		if not self.filters.doctypes or "Sales Invoice" in self.filters.doctypes:
			self.get_data_from_sales_invoices()
		if not self.filters.doctypes or "Purchase Invoice" in self.filters.doctypes:
			self.get_data_from_purchase_invoices()

		self.calculate_totals()
		self.get_columns()

		return self.columns, self.data


	def get_data_from_sales_invoices(self):
		self.transaction = "Sales Invoice"
		self.get_data_from_transactions()

	def get_data_from_purchase_invoices(self):
		self.transaction = "Purchase Invoice"
		self.get_data_from_transactions()

	def get_data_from_transactions(self):
		transactions_headers = {x.name: x.posting_date for x in frappe.get_all(self.transaction,
			filters={
				"company": self.filters.company,
				"posting_date": ("between", (self.filters.period_start_date, self.filters.period_end_date)),
				"docstatus": 1
			},
			fields=["name", "posting_date"]
		)}

		transactions_items = frappe.get_all(f"{self.transaction} Item",
			filters={
				"parenttype": self.transaction,
				"parent": ("in", transactions_headers.keys())
			},
			fields=["parent", "base_net_amount", "item_tax_rate", "item_code"],
			order_by="parent"
		)

		for item in transactions_items:
			if item.parent not in self.parents.get(self.transaction, {}).keys():
				self.data.append({
					"date": transactions_headers.get(item.parent),
					"indent": 0,
					"reference_doctype": self.transaction,
					"reference_document": item.parent,
				})

			row = {
				"indent": 1,
				"item_code": item.item_code,
				"base_net_amount": flt(item.base_net_amount),
			}

			self.parents[self.transaction][item.parent]["base_net_amount"] += flt(item.base_net_amount)

			for tax in frappe.parse_json(item.item_tax_rate):
				if tax.get("rate", 0) not in self.tax_rates:
					self.tax_rates.append(tax.get("rate", 0))

				tax_amount = flt(item.base_net_amount) * flt(tax.get("rate", 0)) / 100.0
				row.update({
					tax.get("rate", 0): tax_amount
				})

				self.parents[self.transaction][item.parent][tax.get("rate", 0)] += tax_amount

			self.data.append(row)

	def calculate_totals(self):
		total_row = frappe._dict({
			"item_code": _("Total"),
			"indent": 0,
			"base_net_amount": 0.0,
		})

		for rate in self.tax_rates:
			total_row.update({rate: 0.0})

		for data in self.data:
			if data.get("indent") == 0:
				base_net_amount = flt(self.parents.get(data.get("reference_doctype"), {}).get(data.get("reference_document"), {}).get("base_net_amount"))
				data.update({ "base_net_amount": base_net_amount})
				total_row["base_net_amount"] += base_net_amount

				for tax in self.parents.get(data.get("reference_doctype"), {}).get(data.get("reference_document"), {}):
					if tax != "base_net_amount":
						tax_amount = flt(self.parents.get(data.get("reference_doctype"), {}).get(data.get("reference_document"), {}).get(tax))
						data.update({ tax: tax_amount })
						total_row[tax] += tax_amount

		self.data.extend([
			{},
			total_row
		])

	def get_columns(self):
		self.columns = [
			{
				"fieldname": "date",
				"label": _("Reference Date"),
				"fieldtype": "Date",
				"width": 120
			},
			{
				"fieldname": "reference_doctype",
				"label": _("Reference DocType"),
				"fieldtype": "Link",
				"options": "DocType",
				"width": 180
			},
			{
				"fieldname": "reference_document",
				"label": _("Reference Document"),
				"fieldtype": "Dynamic Link",
				"options": "reference_doctype",
				"width": 180
			},
			{
				"fieldname": "item_code",
				"label": _("Item Code"),
				"fieldtype": "Link",
				"options": "Item",
				"width": 180
			},
			{
				"fieldname": "base_net_amount",
				"label": _("Base Net Amount"),
				"fieldtype": "Currency",
				"width": 180
			}
		]

		self.tax_rates.sort(reverse=True)
		for rate in self.tax_rates:
			self.columns.append({
					"fieldname": str(rate),
					"label": f"{str(rate)} %",
					"fieldtype": "Currency",
					"width": 180,
					"default": 0.0
				})