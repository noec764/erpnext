# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import difflib
import numpy as np
from frappe.utils import flt, getdate, add_days, nowdate
from erpnext.accounts.doctype.bank_transaction.bank_transaction import get_bank_transaction_balance_on
from frappe.utils.dateutils import parse_date
from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import get_party_account_based_on_invoice_discounting
from erpnext.accounts.utils import get_account_currency
from erpnext import get_default_company
from erpnext.accounts.doctype.bank_account.bank_account import get_party_bank_account

PARTY_FIELD = {
	"Payment Entry": "party",
	"Journal Entry": "party",
	"Sales Invoice": "customer",
	"Purchase Invoice": "supplier",
	"Expense Claim": "Employee"
}

PARTY_TYPES = {
	"Sales Invoice": "Customer",
	"Purchase Invoice": "Supplier",
	"Expense Claim": "Employee"
}

@frappe.whitelist()
def reconcile(bank_transactions, documents):
	bank_reconciliation = BankReconciliation(bank_transactions, documents)
	bank_reconciliation.reconcile()

class BankReconciliation:
	def __init__(self, bank_transactions, documents):
		self.bank_transactions = frappe.parse_json(bank_transactions)
		self.documents = frappe.parse_json(documents)

		if not self.bank_transactions or not self.documents:
			frappe.throw(_("Please select at least one bank transaction and one document to reconcile"))

		self.reconciliation_doctype = self.documents[0]["doctype"]
		self.party = None
		self.party_account = None
		self.party_type = PARTY_TYPES.get(self.reconciliation_doctype)
		self.company = None
		self.cost_center = None
		self.mode_of_payment = None
		self.payment_entries = []


	def check_unique_values(self):
		self.check_party()
		self.check_party_account()
		self.check_field_uniqueness("company", _("company"))
		self.check_field_uniqueness("cost_center", _("cost center"))
		self.check_field_uniqueness("mode_of_payment", _("mode of payment"))

	def check_party(self):
		party = set([x.get(PARTY_FIELD.get(self.reconciliation_doctype)) for x in self.documents])
		if not party or len(party) > 1:
			frappe.throw(_("Please select documents linked to the same party"))
		else:
			self.party = next(iter(party))

	def check_party_account(self):
		if self.reconciliation_doctype == "Sales Invoice":
			party_account = set([get_party_account_based_on_invoice_discounting(doc.get("name")) or doc.get("debit_to") for doc in self.documents])
		elif self.reconciliation_doctype == "Purchase Invoice":
			party_account = set([doc.get("credit_to") for doc in self.documents])
		elif self.reconciliation_doctype == "Employee Advance":
			party_account = set([doc.get("advance_account") for doc in self.documents])
		elif self.reconciliation_doctype == "Expense Claim":
			party_account = set([doc.get("payable_account") for doc in self.documents])

		if not party_account or len(party_account) > 1:
			frappe.throw(_("Please select documents linked to the same party account"))
		else:
			self.party_account = next(iter(party_account))

	def check_field_uniqueness(self, fielname, label):
		value = set([x.get(fielname) for x in self.documents])

		if not value or len(value) > 1:
			frappe.throw(_("Please select documents linked to the same {0}").format(label))
		else:
			self[value] = next(iter(value))

	def reconcile(self):
		if self.reconciliation_doctype in ["Sales Invoice", "Purchase Invoice"] and not (self.documents[0].get("is_pos") or self.documents[0].get("is_paid")):
			self.check_unique_values()
			self.make_payment_entries()
			self.reconcile_created_payments()

		elif len(self.bank_transactions) > 1:
			self.reconcile_multiple_transactions_with_one_document()
		elif len(self.documents) >= 1:
			self.reconcile_one_transaction_with_multiple_documents()

	def reconcile_multiple_transactions_with_one_document(self):
		reconciled_amount = 0
		for bank_transaction in self.bank_transactions:
			if abs(self.documents[0]["unreconciled_amount"]) > reconciled_amount:
				bank_transaction = frappe.get_doc("Bank Transaction", bank_transaction.get("name"))
				allocated_amount = min(max(bank_transaction.unallocated_amount, 0), abs(self.documents[0]["unreconciled_amount"]))

				if allocated_amount > 0:
					bank_transaction.append('payment_entries', {
						'payment_document': self.reconciliation_doctype,
						'payment_entry': self.documents[0]["name"],
						'allocated_amount': allocated_amount
					})

					reconciled_amount += allocated_amount
					bank_transaction.save()

	def reconcile_one_transaction_with_multiple_documents(self):
		bank_transaction = frappe.get_doc("Bank Transaction", self.bank_transactions[0]["name"])
		for document in self.documents:
			bank_transaction.append('payment_entries', {
				'payment_document': document.get("doctype"),
				'payment_entry': document.get("name"),
				'allocated_amount': abs(document.get("unreconciled_amount"))
			})

		bank_transaction.save()

	def reconcile_created_payments(self):
		for transaction, payment in zip(self.bank_transactions, self.payment_entries):
			bank_transaction = frappe.get_doc("Bank Transaction", transaction.get("name"))
			bank_transaction.append('payment_entries', {
				'payment_document': payment.get("doctype"),
				'payment_entry': payment.get("name"),
				'allocated_amount': min(payment.get("unreconciled_amount"), bank_transaction.unallocated_amount)
			})

			bank_transaction.save()

	def make_payment_entries(self):
		for transaction in self.bank_transactions:
			payment_entry = self.get_payment_entry(transaction)
			payment_entry.insert()
			payment_entry.submit()
			self.payment_entries.append(payment_entry)

	def get_payment_entry(self, transaction):
		company_currency = frappe.db.get_value("Company", self.company, "default_currency")
		party_account_currency = get_account_currency(self.party_account)

		# payment type
		if (self.reconciliation_doctype == "Sales Invoice" and transaction.get("amount") < 0) \
			or (self.reconciliation_doctype == "Purchase Invoice" and transaction.get("amount") > 0):
			payment_type = "Receive"
		else:
			payment_type = "Pay"

		# total outstanding
		total_outstanding_amount = 0
		if self.reconciliation_doctype in ("Sales Invoice", "Purchase Invoice"):
			total_outstanding_amount = sum([x.get("outstanding_amount") for x in self.documents])
		elif self.reconciliation_doctype in ("Expense Claim"):
			total_outstanding_amount = sum([(flt(x.get("grand_total"))-flt(x.get("total_amount_reimbursed"))) for x in self.documents])
		elif self.reconciliation_doctype == "Employee Advance":
			total_outstanding_amount = sum([(flt(x.get("advance_amount"))-flt(x.get("paid_amount"))) for x in self.documents])

		bank_account = frappe.get_doc("Bank Account", transaction.get("bank_account"))
		account_currency = frappe.db.get_value("Account", bank_account.account, "account_currency")

		paid_amount = received_amount = 0
		if party_account_currency == account_currency:
			paid_amount = received_amount = abs(transaction.get("unallocated_amount"))
		elif payment_type == "Receive":
			paid_amount = abs(transaction.get("unallocated_amount"))
			target_exchange_rate = total_outstanding_amount / paid_amount
			received_amount = total_outstanding_amount
		else:
			received_amount = abs(transaction.get("unallocated_amount"))
			source_exchange_rate = received_amount / total_outstanding_amount
			paid_amount = total_outstanding_amount

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = payment_type
		pe.company = bank_account.company
		pe.cost_center = self.cost_center
		pe.posting_date = nowdate()
		pe.mode_of_payment = self.mode_of_payment
		pe.party_type = self.party_type
		pe.party = self.party
		contacts = [x.get("contact_person") for x in self.documents]
		pe.contact_person = contacts[0] if contacts else None
		pe.contact_email = " ,".join([x.get("contact_email") for x in self.documents if x.get("contact_email")])
		pe.ensure_supplier_is_not_blocked()

		pe.paid_from = self.party_account if payment_type == "Receive" else bank_account.account
		pe.paid_to = self.party_account if payment_type == "Pay" else bank_account.account
		pe.paid_from_account_currency = party_account_currency \
			if payment_type == "Receive" else account_currency
		pe.paid_to_account_currency = party_account_currency if payment_type == "Pay" else account_currency
		pe.paid_amount = paid_amount
		pe.received_amount = received_amount
		letter_heads = [x.get("letter_head") for x in self.documents]
		pe.letter_head = letter_heads[0] if letter_heads else None
		pe.reference_no = frappe.db.get_value("Bank Transaction", transaction.get("name"), "reference_number")
		pe.reference_date = getdate(transaction.get("date"))
		pe.bank_account = bank_account.name

		if pe.party_type in ["Customer", "Supplier"]:
			bank_account = get_party_bank_account(pe.party_type, pe.party)
			pe.set("party_bank_account", bank_account)
		pe.set_bank_account_data()

		total_allocated_amount = 0
		for doc in self.documents:
			# only Purchase Invoice can be blocked individually
			if doc.get("doctype") == "Purchase Invoice":
				pi = frappe.get_doc("Purchase Invoice", doc.get("name"))
				if pi.invoice_is_blocked():
					frappe.throw(_('{0} is on hold till {1}'.format(pi.name, pi.release_date)))

			# amounts
			grand_total = outstanding_amount = 0
			if self.reconciliation_doctype in ("Sales Invoice", "Purchase Invoice"):
				if party_account_currency == doc.get("company_currency"):
					grand_total = doc.get("base_rounded_total") or doc.get("base_grand_total")
				else:
					grand_total = doc.get("rounded_total") or doc.get("grand_total")
				outstanding_amount = doc.get("outstanding_amount")
			elif self.reconciliation_doctype in ("Expense Claim"):
				grand_total = doc.get("total_sanctioned_amount") + doc.get("total_taxes_and_charges")
				outstanding_amount = doc.get("grand_total") - doc.get("total_amount_reimbursed")
			elif dt == "Employee Advance":
				grand_total = doc.get("advance_amount")
				outstanding_amount = flt(doc.get("advance_amount")) - flt(doc.get("paid_amount"))
			else:
				if party_account_currency == doc.get("company_currency"):
					grand_total = flt(doc.get("base_rounded_total") or doc.get("base_grand_total"))
				else:
					grand_total = flt(doc.get("rounded_total") or doc.get("grand_total"))
				outstanding_amount = grand_total - flt(doc.get("advance_paid"))

			allocated_amount = min(outstanding_amount, flt(transaction.get("unallocated_amount")) - flt(total_allocated_amount))

			pe.append("references", {
				'reference_doctype': doc.get("doctype"),
				'reference_name': doc.get("name"),
				"bill_no": doc.get("bill_no"),
				"due_date": doc.get("due_date"),
				'total_amount': grand_total,
				'outstanding_amount': outstanding_amount,
				'allocated_amount': allocated_amount
			})

			total_allocated_amount += allocated_amount

		pe.setup_party_account_field()
		pe.set_missing_values()
		if self.party_account and bank_account:
			pe.set_exchange_rate()
			pe.set_amounts()
		return pe

@frappe.whitelist()
def get_linked_payments(bank_transactions, document_type, match=True):
	bank_transaction_match = BankTransactionMatch(bank_transactions, document_type, match=True)
	return bank_transaction_match.get_linked_payments()


class BankTransactionMatch:
	def __init__(self, bank_transactions, document_type, match=True):
		self.bank_transactions = frappe.parse_json(bank_transactions) or []
		self.document_type = document_type
		self.match = False if match == "false" else True
		self.amount = sum([x.get("amount") for x in self.bank_transactions]) or 0
		self.currency = self.bank_transactions[0]["currency"] if self.bank_transactions else None
		self.bank_account = self.bank_transactions[0]["bank_account"] if self.bank_transactions else None
		self.company = frappe.db.get_value("Bank Account", self.bank_account, "company") if self.bank_account else get_default_company()

	def get_linked_payments(self):
		if not self.bank_transactions:
			return []

		documents = self.get_linked_documents(unreconciled=self.match)

		if not documents or not self.match:
			return sorted([i for n, i in enumerate(documents) if i not in documents[n + 1:]], \
				key=lambda x: x.get("posting_date", x.get("reference_date")), reverse=True)

		# Check if document with a matching amount (+- 10%) exists
		amount_matches = self.check_matching_amounts(documents)
		if amount_matches and len(amount_matches) == 1:
			return [dict(x, **{"vgtSelected": True}) for x in amount_matches]

		# Get similar bank transactions from history
		similar_transactions_matches = self.get_similar_transactions_references()
		
		result = amount_matches + similar_transactions_matches
		output = sorted([i for n, i in enumerate(result) if i not in result[n + 1:]], \
			key=lambda x: x.get("posting_date", x.get("reference_date")), reverse=True)

		return [dict(x, **{"vgtSelected": True}) for x in output] if len(output) == 1 else self.check_matching_dates(output)

	def get_linked_documents(self, document_names=None, unreconciled=True, filters=None):
		query_filters = {"docstatus": 1, "company": self.company}
		query_or_filters = {}

		if self.document_type == "Journal Entry":
			return self.get_linked_journal_entries(document_names, unreconciled, filters)
		elif self.document_type not in ["Expense Claim", "Payment Entry"]:
			query_filters.update({"currency": self.currency})

		if filters:
			query_filters.update(filters)

		if unreconciled and self.document_type == "Expense Claim":
			query_or_filters.update({"unreconciled_amount": (">", 0), "total_amount_reimbursed": ("=", 0)})
		elif unreconciled and self.document_type in ["Sales Invoice", "Purchase Invoice"]:
			query_or_filters.update({"unreconciled_amount": (">", 0), "outstanding_amount": (">", 0)})
		elif unreconciled:
			query_filters.update({"unreconciled_amount": (">", 0)})

		if document_names:
			query_filters.update({"name": ("in", document_names)})

		query_result = frappe.get_list(self.document_type, filters=query_filters, or_filters=query_or_filters, fields=["*"])

		return self.get_filtered_results(query_result)

	def get_filtered_results(self, query_result):
		filtered_result = []
		party_field = PARTY_FIELD.get(self.document_type)
		reference_field = self.get_reference_field()
		date_field = self.get_reference_date_field()

		if self.document_type == "Payment Entry":
			for result in query_result:
				if (result.get("payment_type") == "Pay" and result.get("paid_from_account_currency") == self.currency):
					result["amount"] = result["unreconciled_amount"] * -1
					filtered_result.append(result)

				elif (result.get("payment_type") == "Receive" and result.get("paid_to_account_currency") == self.currency):
					filtered_result.append(result)

		elif self.document_type == "Purchase Invoice":
			return [dict(x, **{
				"amount": x.get("unreconciled_amount", x.get("outstanding_amount", 0)) if flt(x.get("is_return")) == 1 \
					else (flt(x.get("unreconciled_amount", x.get("outstanding_amount", 0))) * -1),\
				"party": x.get(party_field),\
				"reference_date": x.get(date_field), \
				"reference_string": x.get(reference_field)
			}) for x in query_result]

		elif self.document_type == "Sales Invoice":
			return [dict(x, **{
				"amount": (x.get("unreconciled_amount", x.get("outstanding_amount", 0)) * -1) if flt(x.get("is_return")) == 1 \
					else x.get("unreconciled_amount", x.get("outstanding_amount", 0)),
				"party": x.get(party_field),
				"reference_date": x.get(date_field), \
				"reference_string": x.get(reference_field)
			}) for x in query_result]

		elif self.document_type == "Expense Claim":
			return [dict(x, **{
				"amount": x.get("unreconciled_amount", 0) * -1,
				"party": x.get(party_field),
				"reference_date": x.get(date_field), \
				"reference_string": x.get(reference_field)
			}) for x in query_result]

		else:
			filtered_result = query_result

		return filtered_result

	def get_linked_journal_entries(self, document_names=None, unreconciled=True, filters=None):
		account = frappe.db.get_value("Bank Account", self.bank_account, "account")

		child_query_filters = {"account_currency": self.currency, "account": account}
		parent_query_filters = {"company": self.company}

		if unreconciled:
			parent_query_filters.update({"unreconciled_amount": (">", 0)})

		if document_names:
			parent_query_filters.update({"name": ("in", document_names)})
		else:
			bank_entries = [x.get("parent") for x in frappe.get_all("Journal Entry Account", filters=child_query_filters, \
				fields=["parent"])]
			parent_query_filters.update({"name": ("in", bank_entries)})

		parent_query_result = frappe.get_list("Journal Entry", filters=parent_query_filters, \
			fields=["name", "posting_date", "cheque_no", "cheque_date", "unreconciled_amount", "remark", "user_remark"])
		parent_map = {x.get("name"): x for x in parent_query_result}

		party_query_filters = child_query_filters
		party_query_filters.pop("account")
		if filters:
			party_query_filters.update(filters)

		#party_query_filters.update({"parent": ["in", [x.get("name") for x in parent_query_result]], 'party_type': ['is', 'set']})
		party_query_result = frappe.get_all("Journal Entry Account", filters=party_query_filters, fields=["*"], debug=True)

		amount_field = self.get_amount_field("debit" if self.amount < 0 else "credit")

		result = [dict(x, **{
			"name": parent_map.get(x.get("parent"), {}).get("name"),
			"amount": x.get(amount_field),\
			"posting_date": parent_map.get(x.get("parent"), {}).get("posting_date"), \
			"reference_date": parent_map.get(x.get("parent"), {}).get("cheque_date"), \
			"reference_string": parent_map.get(x.get("parent"), {}).get("cheque_no") \
				or parent_map.get(x.get("parent"), {}).get("remark") or parent_map.get(x.get("parent"), {}).get("userremark"), \
			"unreconciled_amount": parent_map.get(x.get("parent"), {}).get("unreconciled_amount")
			}) for x in party_query_result]

		return [x for x in result if x.get("amount") and x.get("name")]

	def get_amount_field(self, debit_or_credit='debit'):
		return {
			"Payment Entry": "paid_amount",
			"Journal Entry": "debit_in_account_currency" if debit_or_credit == "debit" else "credit_in_account_currency",
			"Sales Invoice": "amount",
			"Purchase Invoice": "paid_amount",
			"Expense Claim": "total_sanctioned_amount"
		}.get(self.document_type)

	def get_reference_date_field(self):
		return {
			"Payment Entry": "reference_date",
			"Journal Entry": "cheque_date",
			"Sales Invoice": "due_date",
			"Purchase Invoice": "due_date",
			"Expense Claim": "total_claimed_amount"
		}.get(self.document_type)

	def get_reference_field(self):
		return {
			"Payment Entry": "reference_no",
			"Journal Entry": "cheque_no",
			"Sales Invoice": "remarks",
			"Purchase Invoice": "remarks",
			"Expense Claim": "remark"
		}.get(self.document_type)

	def check_matching_amounts(self, documents):
		amount_field = self.get_amount_field("debit" if self.amount > 0 else "credit")
		return [x for x in documents if flt(abs(self.amount)) == flt(x.get(amount_field))]

	def check_matching_dates(self, output):
		comparison_date = self.bank_transactions[0].get("date")

		date_field = self.get_reference_date_field()
		closest = min(output, key=lambda x: abs(getdate(x.get(date_field)) - getdate(parse_date(comparison_date))))

		return [dict(x, **{"vgtSelected": True}) if x.get("name") == closest.get("name") else x for x in output]

	def get_similar_transactions_references(self):
		already_reconciled_matches = self.get_already_reconciled_matches()
		references = self.get_similar_documents(already_reconciled_matches)
		return self.get_similar_transactions_based_on_history(references)

	def get_similar_transactions_based_on_history(self, references):
		descriptions = self.get_description_and_party(references)

		query_filters = {descriptions.get("party_field"): ["in", descriptions.get("party")]}

		if self.document_type == "Journal Entry":
			query_filters.update({descriptions.get("party_type_field"): ["in", descriptions.get("party_type")]})

		return self.get_linked_documents(unreconciled=True, filters=query_filters)

	def get_description_and_party(self, references):
		output = {
			"party_type": set(),
			"party": set(),
			"description": set(),
			"party_type_field": "party_type",
			"party_field": PARTY_FIELD.get(self.document_type),
			"description_field": self.get_reference_field()
		}

		for reference in references:
			output["description"].add(reference.get(output["description_field"]))

			if reference.get("doctype") == "Journal Entry":
				journal_entry_accounts = frappe.get_all("Journal Entry Account", filters={"parent": reference.get("name"), "parenttype": document_type, \
					"party_type": ["is", "set"]}, fields=["party_type", "party"])
				for account in journal_entry_accounts:
					output["party"].add(account.get(output["party_field"]))

			else:
				output["party"].add(reference.get(output["party_field"]))

		return output

	def get_already_reconciled_matches(self):
		reconciled_bank_transactions = get_reconciled_bank_transactions()

		selection = []
		for transaction in self.bank_transactions:
			for bank_transaction in reconciled_bank_transactions:
				if bank_transaction.get("description"):
					seq = difflib.SequenceMatcher(lambda x: x == " ", transaction.get("description"), bank_transaction.get("description"))

					if seq.ratio() > 0.6:
						bank_transaction["ratio"] = seq.ratio()
						selection.append(bank_transaction)

		return [x.get("name") for x in selection]

	def get_similar_documents(self, transactions):
		payments_references = [x.get("payment_entry") for x in frappe.get_list("Bank Transaction Payments",
			filters={"parent": ("in", transactions), "parenttype": ("=", "Bank Transaction"), "payment_document": self.document_type},
			fields=["payment_document", "payment_entry"])]
		return self.get_linked_documents(document_names=payments_references, unreconciled=False)

def get_reconciled_bank_transactions():
	return frappe.get_list("Bank Transaction", filters={"allocated_amount": (">", 0), "docstatus": 1}, fields=["name", "description"])

@frappe.whitelist()
def get_statement_chart(account, start_date, end_date):
	transactions = frappe.get_all("Bank Transaction", filters={"docstatus": 1, "date": ["between", [getdate(start_date), getdate(end_date)]], \
		"bank_account": account}, fields=["sum(credit)-sum(debit) as amount", "date", "currency", "sum(unallocated_amount) as unallocated_amount"], \
		group_by="date", order_by="date ASC")

	balance_before = get_bank_transaction_balance_on(account, add_days(getdate(start_date), -1))

	if not transactions or not balance_before:
		return {}

	symbol = frappe.db.get_value("Currency", transactions[0].currency, "symbol", cache=True) \
		or transactions[0].currency

	previous_unallocation = frappe.get_all("Bank Transaction", filters={"docstatus": 1, "date": ("<", getdate(start_date)), "bank_account": account},\
		fields=["sum(unallocated_amount) as unallocated_amount"])


	dates = [add_days(getdate(start_date), -1)]
	daily_balance = [balance_before.get("balance")]
	unallocated_amount = [previous_unallocation[0]["unallocated_amount"] if previous_unallocation else 0]

	for transaction in transactions:
		dates.append(transaction.date)
		daily_balance.append(transaction.amount)
		unallocated_amount.append(transaction.unallocated_amount)

	bank_balance = np.cumsum(daily_balance)
	mean_value = np.mean(bank_balance)

	data = {
		'title': _("Bank balance") + " (" + symbol + ")",
		'data': {
			'datasets': [
				{
					'name': _("Bank Balance"),
					'values': bank_balance
				},
				{
					'name': _("Unallocated Amount"),
					'chartType': 'bar',
					'values': unallocated_amount
				}
			],
			'labels': dates,
			'yMarkers': [
				{
					'label': _("Average balance"),
					'value': mean_value,
					'options': {
						'labelPos': 'left'
						}
				}
			]
		},
		'type': 'line',
		'colors': ['blue', 'green'],
		'lineOptions': {
			'hideDots': 1
		}
	}

	return data

@frappe.whitelist()
def get_initial_balance(account, start_date):
	return get_bank_transaction_balance_on(account, add_days(getdate(start_date), -1))

@frappe.whitelist()
def get_final_balance(account, end_date):
	return get_bank_transaction_balance_on(account, getdate(end_date))
