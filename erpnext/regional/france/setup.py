# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
import os
from frappe.utils import cint
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup(company=None, patch=True):
	setup_company_independent_fixtures()
	if not patch:
		make_fixtures(company)

def setup_company_independent_fixtures():
	make_custom_fields()
	add_custom_roles_for_reports()

def make_custom_fields():
	custom_fields = {
		'Company': [
			dict(fieldname='siren_number', label='SIREN Number',
			fieldtype='Data', insert_after='website')
		],
		'Account': [
			dict(fieldname='negative_in_balance_sheet', label='Negative in Balance Sheet',
			fieldtype='Check', insert_after='include_in_gross', depends_on='eval:doc.report_type=="Balance Sheet" && !doc.is_group',
			description='Balance is debit for asset or credit for liability accounts'),
			dict(fieldname='balance_sheet_alternative_category', label='Balance Sheet Other Category',
			fieldtype='Link', options='Account', insert_after='parent_account', depends_on='eval:doc.report_type=="Balance Sheet" && !doc.is_group')
		]
	}

	create_custom_fields(custom_fields, ignore_validate=True)

def add_custom_roles_for_reports():
	report_name = 'Fichier des Ecritures Comptables [FEC]'

	if not frappe.db.get_value('Custom Role', dict(report=report_name)):
		frappe.get_doc(dict(
			doctype='Custom Role',
			report=report_name,
			roles= [
				dict(role='Accounts Manager')
			]
		)).insert()

def make_fixtures(company=None):
	company = company.name if company else frappe.db.get_value("Global Defaults", None, "default_company")
	company_doc = frappe.get_doc("Company", company)

	if company_doc.chart_of_accounts == "Plan Comptable Général":
		accounts = frappe.get_all("Account", filters={"disabled": 0, "is_group": 0}, fields=["name", "account_number"])
		company_doc.update(default_accounts_mapping(accounts, company_doc))
		company_doc.save()


def default_accounts_mapping(accounts, company):
	account_map = {
		"inter_banks_transfer_account": 580,
		"default_receivable_account": 411,
		"round_off_account": 658,
		"write_off_account": 658,
		"discount_allowed_account": 709,
		"discount_received_account": 609,
		"exchange_gain_loss_account": 666,
		"unrealized_exchange_gain_loss_account": 6865,
		"default_payable_account": 401,
		"default_employee_advance_account": 425,
		"default_expense_account": 600,
		"default_income_account": 706 if company.domain == "Services" else 701,
		"default_deferred_revenue_account": 487,
		"default_deferred_expense_account": 486,
		"default_payroll_payable_account": 421,
		"default_inventory_account": 310,
		"stock_adjustment_account": 603,
		"stock_received_but_not_billed": 4081,
		"service_received_but_not_billed": 4081,
		"expenses_included_in_valuation": 608,
		"accumulated_depreciation_account": 281,
		"depreciation_expense_account": 681,
		"expenses_included_in_asset_valuation": 608,
		"disposal_account": 675,
		"capital_work_in_progress_account": 231,
		"asset_received_but_not_billed": 722
	}

	return {x: ([y.name for y in accounts if cint(y.account_number)==account_map[x]] or [""])[0] for x in account_map}