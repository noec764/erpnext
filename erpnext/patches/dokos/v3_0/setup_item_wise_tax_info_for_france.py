# Copyright (c) 2022, Dokos SAS and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import flt

from erpnext.controllers.taxes_and_totals import get_itemised_tax
from erpnext.regional.france.setup import setup


def execute():
	company = frappe.get_all("Company", filters={"country": "France"})
	if not company:
		return

	setup()

	for line_dt in ("Sales Invoice Item", "Purchase Invoice Item"):
		for line in frappe.get_all(
			line_dt, filters={"item_tax_rate": ("is", "set")}, fields=["name", "item_tax_rate"]
		):
			item_tax_rate = frappe.parse_json(line.item_tax_rate)
			if isinstance(item_tax_rate, dict):
				data = []
				for tax in item_tax_rate:
					data.append({"rate": item_tax_rate[tax], "account": tax})
				frappe.db.set_value(line_dt, line.name, "item_tax_rate", json.dumps(data))

	frappe.db.auto_commit_on_many_writes = 1
	for dt in ("Sales Invoice", "Purchase Invoice"):
		for si in frappe.get_all(dt):
			doc = frappe.get_doc(dt, si.name)
			update_itemised_tax_data(doc)
	frappe.db.auto_commit_on_many_writes = 0


def update_itemised_tax_data(doc):
	if not doc.taxes:
		return

	itemised_tax = get_itemised_tax(doc.taxes, True)

	# Remove non tax fees
	tax_accounts = set(
		itemised_tax[item][tax].get("tax_account") for item in itemised_tax for tax in itemised_tax[item]
	)
	valid_tax_accounts = frappe.get_all(
		"Account", filters={"name": ("in", list(tax_accounts)), "account_type": "Tax"}, pluck="name"
	)
	valid_itemised_tax = {}
	for item in itemised_tax:
		valid_itemised_tax[item] = {}
		for tax in itemised_tax[item]:
			if itemised_tax[item][tax].get("tax_account") in valid_tax_accounts:
				valid_itemised_tax[item][tax] = itemised_tax[item][tax]

	for row in doc.items:
		tax_rate = 0.0
		item_tax_rate = 0.0
		item_specific_rates = []

		if row.item_tax_rate:
			item_tax_rate = frappe.parse_json(row.item_tax_rate)

		# First check if tax rate is present
		# If not then look up in item_wise_tax_detail
		if item_tax_rate:
			for tax in item_tax_rate:
				tax_rate += tax.get("rate")
		elif row.item_code and valid_itemised_tax.get(row.item_code):
			item_specific_rates = [
				tax
				for tax in valid_itemised_tax.get(row.item_code).items()
				if flt(tax[1].get("form_rate", 0)) != 0.0
			]
			tax_rate = sum(
				[
					tax.get("tax_rate", 0)
					for d, tax in (item_specific_rates or valid_itemised_tax.get(row.item_code).items())
				]
			)

		row_tax_rate = flt(tax_rate, row.precision("tax_rate"))
		row.tax_rate = row_tax_rate
		frappe.db.set_value(row.doctype, row.name, "tax_rate", row_tax_rate)
		row_tax_amount = flt((row.base_net_amount * tax_rate) / 100, row.precision("base_net_amount"))
		row.tax_amount = row_tax_amount
		frappe.db.set_value(row.doctype, row.name, "tax_amount", row_tax_amount)
		row_total_amount = flt((row.base_net_amount + row.tax_amount), row.precision("total_amount"))
		row.total_amount = row_total_amount
		frappe.db.set_value(row.doctype, row.name, "total_amount", row_total_amount)

		item_tax_rate = json.dumps(
			[
				{
					"account": tax.get("tax_account"),
					"rate": tax.get("tax_rate", 0),
					"taxable_amount": row.get("base_net_amount"),
					"tax_amount": row.get("tax_amount"),
				}
				for d, tax in (item_specific_rates or valid_itemised_tax.get(row.item_code, {}).items())
			]
		)
		row.item_tax_rate = item_tax_rate
		frappe.db.set_value(row.doctype, row.name, "item_tax_rate", item_tax_rate)
