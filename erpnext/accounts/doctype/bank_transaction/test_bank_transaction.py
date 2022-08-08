# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import unittest

import frappe

from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice

test_dependencies = ["Item", "Cost Center"]


class TestBankTransaction(unittest.TestCase):
	pass


def create_bank_account(bank_name="Citi Bank", account_name="_Test Bank - _TC"):
	try:
		frappe.get_doc(
			{
				"doctype": "Bank",
				"bank_name": bank_name,
			}
		).insert()
	except frappe.DuplicateEntryError:
		pass

	try:
		frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": "Checking Account",
				"bank": bank_name,
				"account": account_name,
			}
		).insert()
	except frappe.DuplicateEntryError:
		pass


def add_transactions():
	create_bank_account()

	doc = frappe.get_doc(
		{
			"doctype": "Bank Transaction",
			"description": "1512567 BG/000002918 OPSKATTUZWXXX AT776000000098709837 Herr G",
			"date": "2018-10-23",
			"debit": 1200,
			"currency": "INR",
			"bank_account": "Checking Account - Citi Bank",
		}
	).insert()
	doc.submit()

	doc = frappe.get_doc(
		{
			"doctype": "Bank Transaction",
			"description": "1512567 BG/000003025 OPSKATTUZWXXX AT776000000098709849 Herr G",
			"date": "2018-10-23",
			"debit": 1700,
			"currency": "INR",
			"bank_account": "Checking Account - Citi Bank",
		}
	).insert()
	doc.submit()

	doc = frappe.get_doc(
		{
			"doctype": "Bank Transaction",
			"description": "Re 95282925234 FE/000002917 AT171513000281183046 Conrad Electronic",
			"date": "2018-10-26",
			"debit": 690,
			"currency": "INR",
			"bank_account": "Checking Account - Citi Bank",
		}
	).insert()
	doc.submit()

	doc = frappe.get_doc(
		{
			"doctype": "Bank Transaction",
			"description": "Auszahlung Karte MC/000002916 AUTOMAT 698769 K002 27.10. 14:07",
			"date": "2018-10-27",
			"debit": 3900,
			"currency": "INR",
			"bank_account": "Checking Account - Citi Bank",
		}
	).insert()
	doc.submit()

	doc = frappe.get_doc(
		{
			"doctype": "Bank Transaction",
			"description": "I2015000011 VD/000002514 ATWWXXX AT4701345000003510057 Bio",
			"date": "2018-10-27",
			"credit": 109080,
			"currency": "INR",
			"bank_account": "Checking Account - Citi Bank",
		}
	).insert()
	doc.submit()


def add_payments():
	try:
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_group": "All Supplier Groups",
				"supplier_type": "Company",
				"supplier_name": "Conrad Electronic",
			}
		).insert()

	except frappe.DuplicateEntryError:
		pass

	pi = make_purchase_invoice(supplier="Conrad Electronic", qty=1, rate=690)
	pe = get_payment_entry("Purchase Invoice", pi.name, bank_account="_Test Bank - _TC")
	pe.reference_no = "Conrad Oct 18"
	pe.reference_date = "2018-10-24"
	pe.insert()
	pe.submit()

	try:
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_group": "All Supplier Groups",
				"supplier_type": "Company",
				"supplier_name": "Mr G",
			}
		).insert()
	except frappe.DuplicateEntryError:
		pass

	pi = make_purchase_invoice(supplier="Mr G", qty=1, rate=1200)
	pe = get_payment_entry("Purchase Invoice", pi.name, bank_account="_Test Bank - _TC")
	pe.reference_no = "Herr G Oct 18"
	pe.reference_date = "2018-10-24"
	pe.insert()
	pe.submit()

	pi = make_purchase_invoice(supplier="Mr G", qty=1, rate=1700)
	pe = get_payment_entry("Purchase Invoice", pi.name, bank_account="_Test Bank - _TC")
	pe.reference_no = "Herr G Nov 18"
	pe.reference_date = "2018-11-01"
	pe.insert()
	pe.submit()

	try:
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_group": "All Supplier Groups",
				"supplier_type": "Company",
				"supplier_name": "Poore Simon's",
			}
		).insert()
	except frappe.DuplicateEntryError:
		pass

	try:
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_group": "All Customer Groups",
				"customer_type": "Company",
				"customer_name": "Poore Simon's",
			}
		).insert()
	except frappe.DuplicateEntryError:
		pass

	pi = make_purchase_invoice(supplier="Poore Simon's", qty=1, rate=3900)
	pe = get_payment_entry("Purchase Invoice", pi.name, bank_account="_Test Bank - _TC")
	pe.reference_no = "Poore Simon's Oct 18"
	pe.reference_date = "2018-10-28"
	pe.insert()
	pe.submit()

	try:
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_group": "All Customer Groups",
				"customer_type": "Company",
				"customer_name": "Fayva",
			}
		).insert()
	except frappe.DuplicateEntryError:
		pass

	si = create_sales_invoice(customer="Fayva", qty=1, rate=109080)
	pe = get_payment_entry("Sales Invoice", si.name, bank_account="_Test Bank - _TC")
	pe.reference_no = "Fayva Oct 18"
	pe.reference_date = "2018-10-29"
	pe.insert()
	pe.submit()

	mode_of_payment = frappe.get_doc({"doctype": "Mode of Payment", "name": "Cash"})

	if not frappe.db.get_value(
		"Mode of Payment Account", {"company": "_Test Company", "parent": "Cash"}
	):
		mode_of_payment.append(
			"accounts", {"company": "_Test Company", "default_account": "_Test Bank - _TC"}
		)
		mode_of_payment.save()

	si = create_sales_invoice(customer="Fayva", qty=1, rate=109080, do_not_save=1)
	si.is_pos = 1
	si.append(
		"payments", {"mode_of_payment": "Cash", "account": "_Test Bank - _TC", "amount": 109080}
	)
	si.insert()
	si.submit()
