import json

import frappe
from frappe.utils import flt

from erpnext.controllers.taxes_and_totals import get_itemised_tax


def update_itemised_tax_data(doc):
	if not doc.taxes:
		return

	itemised_tax = get_itemised_tax(doc.taxes, True, True)

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
			row.item_tax_rate = json.dumps(
				[
					{"account": tax.get("tax_account"), "rate": tax.get("tax_rate", 0)}
					for d, tax in (item_specific_rates or valid_itemised_tax.get(row.item_code).items())
				]
			)

		meta = frappe.get_meta(row.doctype)

		if meta.has_field("tax_rate"):
			row.tax_rate = flt(tax_rate, row.precision("tax_rate"))
			row.tax_amount = flt((row.net_amount * tax_rate) / 100, row.precision("net_amount"))
			row.total_amount = flt((row.net_amount + row.tax_amount), row.precision("total_amount"))
