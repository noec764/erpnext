# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document

class AssetCategory(Document):
	def validate(self):
		self.validate_finance_books()
		self.validate_accounts()

	def validate_finance_books(self):
		for d in self.finance_books:
			for field in ("Total Number of Depreciations", "Frequency of Depreciation"):
				if cint(d.get(frappe.scrub(field)))<1:
					frappe.throw(_("Row {0}: {1} must be greater than 0").format(d.idx, field), frappe.MandatoryError)

	def validate_accounts(self):
		account_type_map = {
			'fixed_asset_account': { 'account_type': 'Fixed Asset' },
			'accumulated_depreciation_account': { 'account_type': 'Accumulated Depreciation' },
			'depreciation_expense_account': { 'root_type': 'Expense' },
			'capital_work_in_progress_account': { 'account_type': 'Capital Work in Progress' }
		}
		for d in self.accounts:
			for fieldname in account_type_map.keys():
				if d.get(fieldname):
					selected_account = d.get(fieldname)
					key_to_match = next(iter(account_type_map.get(fieldname))) # acount_type or root_type
					selected_key_type = frappe.db.get_value('Account', selected_account, key_to_match)
					expected_key_type = account_type_map[fieldname][key_to_match]

					if selected_key_type != expected_key_type:
						frappe.throw(_("Row #{}: {} of {} should be {}. Please modify the account or select a different account.")
							.format(d.idx, frappe.unscrub(key_to_match), frappe.bold(selected_account), frappe.bold(expected_key_type)),
							title=_("Invalid Account"))

@frappe.whitelist()
def get_asset_category_account(fieldname, item=None, asset=None, account=None, asset_category = None, company = None):
	if item and frappe.db.get_value("Item", item, "is_fixed_asset"):
		asset_category = frappe.db.get_value("Item", item, ["asset_category"])

	elif not asset_category or not company:
		if account:
			if frappe.db.get_value("Account", account, "account_type") != "Fixed Asset":
				account=None

		if not account:
			asset_details = frappe.db.get_value("Asset", asset, ["asset_category", "company"])
			asset_category, company = asset_details or [None, None]

	account = frappe.db.get_value("Asset Category Account",
		filters={"parent": asset_category, "company_name": company}, fieldname=fieldname)

	return account