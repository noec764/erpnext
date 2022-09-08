# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils import cstr, getdate
from .default_website import website_maker
from erpnext.accounts.doctype.account.account import RootNotEditable


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


def create_bank_and_bank_account(bank_account_name, account):
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
			frappe.get_doc(journal).insert()
		except frappe.DuplicateEntryError:
			pass
		except frappe.UniqueValidationError:
			pass
		except Exception:
			print(frappe.get_traceback())


def create_email_digest():
	from frappe.utils.user import get_system_managers

	system_managers = get_system_managers(only_name=True)
	if not system_managers:
		return

	recipients = []
	for d in system_managers:
		recipients.append({"recipient": d})

	companies = frappe.db.sql_list("select name FROM `tabCompany`")
	for company in companies:
		if not frappe.db.exists("Email Digest", "Default Weekly Digest - " + company):
			edigest = frappe.get_doc(
				{
					"doctype": "Email Digest",
					"name": "Default Weekly Digest - " + company,
					"company": company,
					"frequency": "Weekly",
					"recipients": recipients,
				}
			)

			for df in edigest.meta.get("fields", {"fieldtype": "Check"}):
				if df.fieldname != "scheduler_errors":
					edigest.set(df.fieldname, 1)

			edigest.insert()

	# scheduler errors digest
	if companies:
		edigest = frappe.new_doc("Email Digest")
		edigest.update(
			{
				"name": "Scheduler Errors",
				"company": companies[0],
				"frequency": "Daily",
				"recipients": recipients,
				"scheduler_errors": 1,
				"enabled": 1,
			}
		)
		edigest.insert()


def create_logo(args):
	if args.get("attach_logo"):
		attach_logo = args.get("attach_logo").split(",")
		if len(attach_logo) == 3:
			filename, filetype, content = attach_logo
			_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": filename,
					"attached_to_doctype": "Website Settings",
					"attached_to_name": "Website Settings",
					"decode": True,
				}
			)
			_file.save()
			fileurl = _file.file_url
			frappe.db.set_value(
				"Website Settings",
				"Website Settings",
				"brand_html",
				"<img src='{0}' style='max-width: 40px; max-height: 25px;'> {1}".format(
					fileurl, args.get("company_name")
				),
			)


def create_website(args):
	website_maker(args)


def get_fy_details(fy_start_date, fy_end_date):
	start_year = getdate(fy_start_date).year
	if start_year == getdate(fy_end_date).year:
		fy = cstr(start_year)
	else:
		fy = cstr(start_year) + "-" + cstr(start_year + 1)
	return fy
