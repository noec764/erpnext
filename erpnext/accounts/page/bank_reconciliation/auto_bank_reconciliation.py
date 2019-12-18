# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import re
import frappe
from frappe import _
from erpnext.accounts.page.bank_reconciliation.bank_reconciliation import BankReconciliation

@frappe.whitelist()
def auto_bank_reconciliation(bank_transactions, method="by_name"):
	#frappe.enqueue("erpnext.accounts.page.bank_reconciliation.auto_bank_reconciliation._reconcile_transactions", bank_transactions=bank_transactions, method_type=method)
	_reconcile_transactions(bank_transactions, method)
def _reconcile_transactions(bank_transactions, method_type):
	bank_transactions = frappe.parse_json(bank_transactions) or []
	if not bank_transactions:
		frappe.throw(_("Please select a period with at least one transaction to reconcile"))

	for bank_transaction in bank_transactions:
		bank_reconciliation = AutoBankReconciliation(bank_transaction, method_type)
		bank_reconciliation.reconcile()

class AutoBankReconciliation:
	def __init__(self, bank_transaction, method):
		self.bank_transaction = bank_transaction
		self.method = method
		self.prefixes = []
		self.matching_names = []
		self.documents = []

	def reconcile(self):
		if self.method == "by_name":
			self.get_naming_series()
			self.check_transaction_references()
			if self.matching_names:
				self.get_corresponding_documents()

		if self.documents:
			BankReconciliation([self.bank_transaction], self.documents).reconcile()

	def get_naming_series(self):
		self.prefixes = [x.get("name") for x in frappe.db.sql("SELECT name FROM `tabSeries`;", as_dict=True) if x.get("name")]

	def check_transaction_references(self):
		for prefix in self.prefixes:
			for reference in [self.bank_transaction.get("reference_number"), self.bank_transaction.get("description")]:
				if reference:
					search_regex = r"{0}.*".format(prefix)
					match = re.findall(search_regex, reference)
					if match:
						self.matching_names.extend(match)

	def get_corresponding_documents(self):
		for matching_name in self.matching_names:
			for doctype in ["Payment Entry", "Sales Invoice", "Purchase Invoice", "Expense Claim"]:
				if frappe.db.exists(doctype, matching_name):
					self.documents.append(frappe.get_doc(doctype, matching_name).as_dict())