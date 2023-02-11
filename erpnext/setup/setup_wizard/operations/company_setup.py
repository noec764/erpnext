# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils import cstr, getdate


def create_fiscal_year_and_company(args):
	if args.get("fy_start_date"):
		curr_fiscal_year = get_fy_details(args.get("fy_start_date"), args.get("fy_end_date"))
		frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": curr_fiscal_year,
				"year_start_date": args.get("fy_start_date"),
				"year_end_date": args.get("fy_end_date"),
			}
		).insert()

	if args.get("company_name"):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": args.get("company_name"),
				"enable_perpetual_inventory": 1,
				"abbr": args.get("company_abbr"),
				"default_currency": args.get("currency"),
				"country": args.get("country"),
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": args.get("chart_of_accounts"),
			}
		).insert()


def enable_shopping_cart(args):  # nosemgrep
	# Needs price_lists
	frappe.get_doc(
		{
			"doctype": "E Commerce Settings",
			"enabled": 1,
			"company": args.get("company_name"),
			"price_list": frappe.db.get_value("Price List", {"selling": 1}),
			"default_customer_group": _("Individual"),
			"quotation_series": "QTN-",
		}
	).insert()


def create_bank_and_bank_account(company_name, bank_account_name, account):
	bank = frappe.get_doc({"doctype": "Bank", "bank_name": bank_account_name})

	try:
		bank.insert()
	except frappe.DuplicateEntryError:
		pass

	bank_account = frappe.get_doc(
		{
			"doctype": "Bank Account",
			"account_name": bank_account_name,
			"bank": bank.name,
			"account": account,
			"is_default": 1,
			"is_company_account": 1,
			"company": company_name,
		}
	)

	try:
		bank_account.insert()
	except frappe.DuplicateEntryError:
		pass


def create_accounting_journals(bank_account_name, company):
	journals = [
		{
			"doctype": "Accounting Journal",
			"journal_code": _("MOP"),
			"journal_name": _("Miscellaneous Operations"),
			"type": "Miscellaneous",
			"company": company,
			"conditions": [
				{"document_type": "Journal Entry"},
				{"document_type": "Period Closing Voucher"},
				{"document_type": "Delivery Note"},
				{"document_type": "Purchase Receipt"},
				{"document_type": "Stock Entry"},
				{"document_type": "Expense Claim"},
			],
		},
		{
			"doctype": "Accounting Journal",
			"journal_code": _("SAL"),
			"journal_name": _("Sales"),
			"type": "Sales",
			"company": company,
			"conditions": [{"document_type": "Sales Invoice"}],
		},
		{
			"doctype": "Accounting Journal",
			"journal_code": _("PUR"),
			"journal_name": _("Purchases"),
			"type": "Purchase",
			"company": company,
			"conditions": [{"document_type": "Purchase Invoice"}],
		},
		{
			"doctype": "Accounting Journal",
			"journal_code": _("BAN"),
			"journal_name": _("Bank"),
			"type": "Bank",
			"company": company,
			"account": bank_account_name,
			"conditions": [{"document_type": "Payment Entry"}],
		},
	]

	for journal in journals:
		try:
			frappe.get_doc(journal).insert(ignore_if_duplicate=True)
		except Exception:
			print(frappe.get_traceback())


def get_fy_details(fy_start_date, fy_end_date):
	start_year = getdate(fy_start_date).year
	if start_year == getdate(fy_end_date).year:
		fy = cstr(start_year)
	else:
		fy = cstr(start_year) + "-" + cstr(start_year + 1)
	return fy
