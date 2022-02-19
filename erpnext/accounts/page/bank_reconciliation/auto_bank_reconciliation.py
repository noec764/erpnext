# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import re
import frappe
import erpnext
from frappe import _
from erpnext.accounts.page.bank_reconciliation.bank_reconciliation import BankReconciliation
from erpnext.accounts.page.bank_reconciliation.stripe_reconciliation import reconcile_stripe_payouts
from erpnext.accounts.page.bank_reconciliation.gocardless_reconciliation import reconcile_gocardless_payouts

@frappe.whitelist()
def auto_bank_reconciliation(bank_transactions):
	_reconcile_transactions(bank_transactions)

def _reconcile_transactions(bank_transactions):
	bank_transactions = frappe.parse_json(bank_transactions) or []
	if not bank_transactions:
		frappe.throw(_("Please select a period with at least one transaction to reconcile"))

	for bank_transaction in bank_transactions:
		if not bank_transaction.get("amount"):
			continue

		if frappe.get_hooks('auto_reconciliation_methods'):
			for hook in frappe.get_hooks('auto_reconciliation_methods'):
				frappe.get_attr(hook)(bank_transaction)
		else:
			bank_reconciliation = AutoBankReconciliation(bank_transaction)
			bank_reconciliation.reconcile()

	reconcile_stripe_payouts(bank_transactions)
	reconcile_gocardless_payouts(bank_transactions)

class AutoBankReconciliation:
	def __init__(self, bank_transaction):
		self.bank_transaction = bank_transaction
		self.reconciliation_by_id = {
			"prefixes": [],
			"matching_names": set()
		}
		self.documents = []

	def reconcile(self):
		# Reconcile by document name in references
		self.get_naming_series()
		self.check_transaction_references()
		if self.reconciliation_by_id.get("matching_names"):
			self.get_corresponding_documents()

		# Call regional reconciliation features
		regional_reconciliation(self)

		if self.documents:
			BankReconciliation([self.bank_transaction], list({d['name']:d for d in self.documents}.values())).reconcile()

	def get_naming_series(self):
		self.reconciliation_by_id["prefixes"] = [x.get("name") for x in frappe.db.sql("""SELECT name FROM `tabSeries`""", as_dict=True) if x.get("name")]

	def check_transaction_references(self):
		for prefix in self.reconciliation_by_id.get("prefixes", []):
			for reference in [self.bank_transaction.get("reference_number"), self.bank_transaction.get("description")]:
				if reference:
					# TODO: get multiple references separated by a comma or a space
					search_regex = r"{0}.*".format(prefix)
					match = re.findall(search_regex, reference)
					if match:
						for m in match:
							self.reconciliation_by_id["matching_names"].add(m)

	def get_corresponding_documents(self):
		for matching_name in self.reconciliation_by_id["matching_names"]:
			corresponding_payment_entry = self.get_corresponding_payment_entries(matching_name)
			if corresponding_payment_entry:
				self.documents.append(corresponding_payment_entry.as_dict())
				break
			else:
				for dt in ["Sales Invoice", "Purchase Invoice"]:
					if frappe.db.exists(dt, matching_name):
						doc = frappe.get_doc(dt, matching_name)
						if doc.outstanding_amount == 0:
							for payment_entry in frappe.get_all("Payment Entry Reference", filters={
								"reference_doctype": doc.doctype,
								"reference_name": doc.name
							}, pluck="parent"):
								corresponding_payment_entry = self.get_corresponding_payment_entries(payment_entry)
								if corresponding_payment_entry:
									self.documents.append(corresponding_payment_entry.as_dict())
									break
						else:
							self.documents.append(doc.as_dict())
							break

	def get_corresponding_payment_entries(self, matching_name):
		if frappe.db.exists("Payment Entry", matching_name):
			doc = frappe.get_doc("Payment Entry", matching_name)
			if doc.docstatus == 1 and doc.status == "Unreconciled":
				return doc

# Used for regional overrides
@erpnext.allow_regional
def regional_reconciliation(auto_bank_reconciliation):
	pass
