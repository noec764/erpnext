# Copyright (c) 2022, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, fmt_money

from erpnext.accounts.utils import get_balance_on


class FranceTaxDeclarationPreparation(Document):
	def before_insert(self):
		self.get_deductible_vat()
		self.get_collected_vat()

	@frappe.whitelist()
	def get_deductible_vat(self):
		deductible_accounts = self.get_deductible_accounts()
		expense_accounts = self.get_accounts("Expense Account")
		gl_entries = self.get_gl_entries(list(deductible_accounts.keys()))

		output = {
			"gl_entries": [],
			"taxable_amount": 0.0,
			"tax_amount": 0.0,
			"tax_details": defaultdict(lambda: defaultdict(float)),
		}
		for gl_entry in gl_entries:
			gl_entry["tax_rate"] = deductible_accounts.get(gl_entry.account)
			linked_entries = self.get_linked_entries(gl_entry.accounting_entry_number)

			if gl_entry.voucher_type in ("Sales Invoice", "Purchase Invoice"):
				if "taxable_amount" not in gl_entry:
					gl_entry["taxable_amount"] = 0.0
				doc = frappe.get_doc(gl_entry.voucher_type, gl_entry.voucher_no)
				for item in doc.get("items", []):
					for row in frappe.parse_json(item.get("item_tax_rate")):
						if row.get("account") == gl_entry.account:
							gl_entry["taxable_amount"] += flt(row.get("taxable_amount"))
			elif len(
				[e for e in linked_entries if e.account in list(deductible_accounts.keys())]
			) == 1 and [e for e in linked_entries if e.account in expense_accounts]:
				gl_entry["taxable_amount"] = sum(
					flt(e.debit) - flt(e.credit) for e in linked_entries if e.account in expense_accounts
				)
			else:
				continue

			taxable_amount = flt(gl_entry.get("taxable_amount"))
			tax_amount = flt(gl_entry.get("debit")) - flt(gl_entry.get("credit"))
			output["taxable_amount"] += taxable_amount
			output["tax_amount"] += tax_amount
			output["gl_entries"].append(gl_entry)
			output["tax_details"][gl_entry["account"]]["taxable_amount"] += taxable_amount
			output["tax_details"][gl_entry["account"]]["tax_amount"] += tax_amount

		self.set("deductible_vat", [])

		for gl_entry in output["gl_entries"]:
			gl_entry["vat_amount"] = flt(gl_entry.get("debit")) - flt(gl_entry.get("credit"))
			row = self.append("deductible_vat", {})
			row.update(gl_entry)

		self.deductible_taxable_amount = output["taxable_amount"]
		self.deductible_tax_amount = output["tax_amount"]
		self.deductible_tax_details = frappe.as_json(output["tax_details"])

		self.deductible_details = frappe.render_template(
			"erpnext/regional/doctype/france_tax_declaration_preparation/tax_details.html",
			{"details": output["tax_details"]},
		)

		return self.deductible_details

	@frappe.whitelist()
	def get_collected_vat(self):
		collection_accounts = self.get_collection_accounts()
		income_accounts = self.get_accounts("Income Account")
		gl_entries = self.get_gl_entries(list(collection_accounts.keys()))

		output = {
			"gl_entries": [],
			"taxable_amount": 0.0,
			"tax_amount": 0.0,
			"tax_details": defaultdict(lambda: defaultdict(float)),
		}
		for gl_entry in gl_entries:
			gl_entry["tax_rate"] = collection_accounts.get(gl_entry.account)
			linked_entries = self.get_linked_entries(gl_entry.accounting_entry_number)

			if len([e for e in linked_entries if e.account in list(collection_accounts.keys())]) == 1 and [
				e for e in linked_entries if e.account in income_accounts
			]:
				gl_entry["taxable_amount"] = sum(
					flt(e.credit) - flt(e.debit) for e in linked_entries if e.account in income_accounts
				)
			elif gl_entry.voucher_type in ("Sales Invoice", "Purchase Invoice"):
				if "taxable_amount" not in gl_entry:
					gl_entry["taxable_amount"] = 0.0
				doc = frappe.get_doc(gl_entry.voucher_type, gl_entry.voucher_no)
				for item in doc.get("items", []):
					for row in frappe.parse_json(item.get("item_tax_rate")):
						if row.get("account") == gl_entry.account:
							gl_entry["taxable_amount"] += flt(row.get("taxable_amount"))
				else:
					continue
			else:
				continue

			taxable_amount = flt(gl_entry.get("taxable_amount"))
			tax_amount = flt(gl_entry.get("credit")) - flt(gl_entry.get("debit"))
			output["taxable_amount"] += taxable_amount
			output["tax_amount"] += tax_amount
			output["gl_entries"].append(gl_entry)
			output["tax_details"][gl_entry["account"]]["taxable_amount"] += taxable_amount
			output["tax_details"][gl_entry["account"]]["tax_amount"] += tax_amount

		self.set("collected_vat", [])

		for gl_entry in output["gl_entries"]:
			gl_entry["vat_amount"] = flt(gl_entry.get("credit")) - flt(gl_entry.get("debit"))
			row = self.append("collected_vat", {})
			row.update(gl_entry)

		self.collected_taxable_amount = output["taxable_amount"]
		self.collected_tax_amount = output["tax_amount"]
		self.collected_tax_details = frappe.as_json(output["tax_details"])

		self.collected_details = frappe.render_template(
			"erpnext/regional/doctype/france_tax_declaration_preparation/tax_details.html",
			{"details": output["tax_details"]},
		)

		return self.collected_details

	def get_linked_entries(self, accounting_entry_number):
		return frappe.get_all(
			"GL Entry",
			filters={
				"accounting_entry_number": accounting_entry_number,
				"is_cancelled": 0,
			},
			fields=[
				"name",
				"accounting_entry_number",
				"account",
				"accounting_journal",
				"posting_date as date",
				"debit",
				"credit",
			],
		)

	def get_gl_entries(self, accounts):
		gl_entry = frappe.qb.DocType("GL Entry")
		vat_preparation_details = frappe.qb.DocType("France Tax Declaration Preparation Details")
		subquery = (
			frappe.qb.from_(vat_preparation_details)
			.select(vat_preparation_details.gl_entry)
			.where(vat_preparation_details.parent != self.name)
		)
		return (
			frappe.qb.from_(gl_entry)
			.where(gl_entry.account.isin(accounts))
			.where(gl_entry.is_cancelled == 0)
			.where(gl_entry.posting_date <= self.date)
			.where(gl_entry.name.notin(subquery))
			.select(
				gl_entry.name.as_("gl_entry"),
				gl_entry.accounting_entry_number,
				gl_entry.posting_date.as_("date"),
				gl_entry.remarks,
				gl_entry.voucher_type,
				gl_entry.voucher_no,
				gl_entry.against,
				gl_entry.debit,
				gl_entry.credit,
				gl_entry.account,
				gl_entry.fiscal_year,
			)
		).run(as_dict=True)

	def get_deductible_accounts(self):
		return {
			t.name: t.tax_rate for t in self.get_vat_accounts() if t.account_number.startswith("4456")
		}

	def get_collection_accounts(self):
		return {
			t.name: t.tax_rate for t in self.get_vat_accounts() if t.account_number.startswith("4457")
		}

	def get_pending_tax_accounts(self):
		return {
			t.name: t.tax_rate for t in self.get_creditors_accounts() if t.account_number.startswith("4458")
		}

	@staticmethod
	def get_vat_accounts():
		return frappe.get_all(
			"Account",
			filters={"account_type": "Tax", "disabled": 0},
			fields=["name", "account_number", "tax_rate"],
		)

	@staticmethod
	def get_creditors_accounts():
		return frappe.get_all(
			"Account",
			filters={"account_type": "Payable", "disabled": 0},
			fields=["name", "account_number", "tax_rate"],
		)

	@staticmethod
	def get_accounts(account_type):
		return frappe.get_all(
			"Account", filters={"account_type": account_type, "disabled": 0}, pluck="name"
		)

	@frappe.whitelist()
	def get_summary(self):
		collection = frappe.parse_json(self.collected_tax_details) or {}
		deductions = frappe.parse_json(self.deductible_tax_details) or {}

		summary = []
		default_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		collection_total_taxable = 0.0
		collection_total_tax = 0.0
		for account, values in collection.items():
			collection_total_taxable += flt(values.get("taxable_amount"))
			collection_total_tax += flt(values.get("tax_amount"))
			summary.append(
				{
					"account": account,
					"taxable_amount": fmt_money(values.get("taxable_amount"), currency=default_currency),
					"tax_amount": fmt_money(values.get("tax_amount"), currency=default_currency),
				}
			)

		summary.append(
			{
				"account": _("Total Collected"),
				"taxable_amount": fmt_money(collection_total_taxable, currency=default_currency),
				"tax_amount": fmt_money(collection_total_tax, currency=default_currency),
				"bold": 1,
			}
		)
		summary.append({})
		deductions_total_taxable = 0.0
		deductions_total_tax = 0.0
		for account, values in deductions.items():
			deductions_total_taxable += flt(values.get("taxable_amount"))
			deductions_total_tax += flt(values.get("tax_amount"))
			summary.append(
				{
					"account": account,
					"taxable_amount": fmt_money(values.get("taxable_amount"), currency=default_currency),
					"tax_amount": fmt_money(values.get("tax_amount"), currency=default_currency),
				}
			)

		pending_tax_accounts = self.get_pending_tax_accounts()
		for account in pending_tax_accounts:
			balance = get_balance_on(account, self.date, company=self.company)
			if balance > 0:
				deductions_total_tax += flt(balance)
				summary.append(
					{"account": account, "tax_amount": fmt_money(balance, currency=default_currency)}
				)

		summary.append(
			{
				"account": _("Total Deductible"),
				"taxable_amount": fmt_money(deductions_total_taxable, currency=default_currency),
				"tax_amount": fmt_money(deductions_total_tax, currency=default_currency),
				"bold": 1,
			}
		)

		summary.append({})
		summary.append(
			{
				"account": _("Balance"),
				"taxable_amount": "",
				"tax_amount": fmt_money(
					flt(collection_total_tax) - flt(deductions_total_tax), currency=default_currency
				),
				"bold": 1,
			}
		)

		return {"columns": self.get_columns(), "data": summary}

	@staticmethod
	def get_columns():
		return [
			{
				"id": "account",
				"name": _("Account"),
				"editable": 0,
				"resizable": 0,
				"sortable": 0,
				"focusable": 0,
				"dropdown": 0,
				"width": 300,
			},
			{
				"id": "taxable_amount",
				"name": _("Taxable Amount"),
				"editable": 0,
				"resizable": 0,
				"sortable": 0,
				"focusable": 0,
				"dropdown": 0,
				"width": 200,
			},
			{
				"id": "tax_amount",
				"name": _("Tax Amount"),
				"editable": 0,
				"resizable": 0,
				"sortable": 0,
				"focusable": 0,
				"dropdown": 0,
				"width": 200,
			},
		]
