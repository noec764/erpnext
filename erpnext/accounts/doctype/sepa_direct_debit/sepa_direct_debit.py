# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, getdate, nowdate, fmt_money, cint, now_datetime
from frappe import msgprint, _
from frappe.model.document import Document
import datetime

class SepaDirectDebit(Document):
	def validate(self):
		self.total_amount = 0
		for entry in self.payment_entries:
			self.total_amount += flt(entry.amount)

	def on_submit(self):
		self.generate_xml_file()

	def get_payment_entries(self):
		if not (self.from_date and self.to_date):
			frappe.throw(_("From Date and To Date are Mandatory"))

		condition = ""
		if not self.include_generated_entries:
			condition = 'and not exists (select 1 from `tabSepa Direct Debit Details` as sddd where sddd.payment_document = "Payment Entry" and sddd.payment_entry = pe.name)'

		payment_entries = frappe.db.sql("""
			select
				"Payment Entry" as payment_document, pe.name as payment_entry,
				pe.reference_no as cheque_number, pe.reference_date,
				pe.paid_amount as credit,
				pe.posting_date, pe.party as against_account, pe.clearance_date
			from `tabPayment Entry` as pe
			where
				pe.mode_of_payment=%(mop)s and pe.docstatus=1
				and pe.paid_from_account_currency=%(currency)s
				and pe.reference_date >= %(from)s and pe.reference_date <= %(to)s
				{0}
			order by
				pe.reference_date ASC, pe.name DESC
		""".format(condition),
				{"mop":self.mode_of_payment, "from":self.from_date, "to":self.to_date, "currency": self.currency}, as_dict=1)

		entries = sorted(list(payment_entries), key=lambda k: k['reference_date'] or getdate(nowdate()))
		self.set('payment_entries', [])
		self.total_amount = 0.0

		for d in entries:
			row = self.append('payment_entries', {})
			amount = d.credit
			d.amount = amount
			row.update(d)
			self.total_amount += flt(amount)

	def generate_xml_file(self):
		from sepaxml import SepaDD

		sepa_settings = frappe.get_doc("Sepa Direct Debit Settings", self.company)
		company_iban, company_bic = frappe.db.get_value("Bank Account", sepa_settings.bank_account, ["iban", "swift_number"])

		config = {
			"name": sepa_settings.company_name,
			"IBAN": company_iban,
			"BIC": company_bic,
			"batch": self.batch_booking,
			"creditor_id": sepa_settings.creditor_identifier,  # supplied by your bank or financial authority
			"currency": self.currency,  # ISO 4217
			"instrument": sepa_settings.instrument  # - default is CORE (B2C)
		}
		sepa = SepaDD(config, schema=sepa_settings.schema or "pain.008.001.02", clean=True)

		for payment_entry in self.payment_entries:
			payment_types = {"One-off": "OOFF", "First": "FRST", "Recurrent": "RCUR", "Final": "FNAL"}
			payment_type = self.direct_debit_type

			customer = payment_entry.against_account
			if not frappe.db.exists("Sepa Mandate", dict(customer=customer, registered_on_gocardless=0, status="Active")):
				frappe.throw(_("Please create or activate a SEPA Mandate for customer {0}".format(customer)))

			if frappe.get_all("Sepa Mandate", dict(customer=customer, registered_on_gocardless=0, status="Active")):
				frappe.throw(_("Customer {0} has several active mandates. Please keep only one active mandate.".format(customer)))

			mandate = frappe.get_doc("Sepa Mandate", dict(customer=customer, registered_on_gocardless=0, status="Active"))
			if not mandate.bank_account:
				frappe.throw(_("Please add a bank account in mandate {0} for customer {1}".format(mandate.name, customer)))

			customer_iban, customer_bic = frappe.db.get_value("Bank Account", mandate.bank_account, ["iban", "swift_number"])

			if not customer_iban:
				frappe.throw(_("Please add an IBAN in bank account {0} for customer {1}".format(mandate.bank_account, customer)))

			if not customer_bic:
				frappe.throw(_("Please add a Swift Number in bank account {0} for customer {1}".format(mandate.bank_account, customer)))

			pe = frappe.get_doc("Payment Entry", payment_entry.payment_entry)
			sales_invoices = ""

			for ref in pe.references:
				sales_invoices += "/" + ref.reference_name

			payment_amount = cint(payment_entry.amount * 100)

			payment = {
				"name": customer,
				"IBAN": customer_iban,
				"BIC": customer_bic,
				"amount": payment_amount,  # in cents
				"type": payment_types.get(payment_type),  # FRST,RCUR,OOFF,FNAL
				"collection_date": getdate(payment_entry.reference_date),
				"mandate_id": mandate.mandate,
				"mandate_date": mandate.creation_date,
				"description": sepa_settings.reference_prefix + sales_invoices,
				"endtoend_id": pe.reference_no  # autogenerated if obmitted
			}
			sepa.add_payment(payment)
		try:
			sepa_export = sepa.export(validate=False) # TODO: correct false positive upon validation
		except Exception as e:
			frappe.throw(str(e))
		self.save_sepa_export(sepa_export)

		return sepa_export

	def save_sepa_export(self, sepa_export, replace=False):
		_file = frappe.get_doc({
			"doctype": "File",
			"file_name": self.name + "-" + str(now_datetime()) + ".xml",
			"attached_to_doctype": self.doctype,
			"attached_to_name": self.name,
			"is_private": True,
			"content": sepa_export
		})
		_file.save()

@frappe.whitelist()
def create_sepa_payment_entries(from_date, to_date, mode_of_payment):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	try:
		open_invoices = frappe.get_all("Sales Invoice", filters={'status': ['in', ('Unpaid', 'Overdue')], 'due_date': ['between', (from_date, to_date)]}, fields=["name", "customer", "due_date"])
		for open_invoice in open_invoices:
			if frappe.db.exists("Sepa Mandate", dict(customer=open_invoice.customer, status="Active", registered_on_gocardless=0)):

				payment_entry = get_payment_entry("Sales Invoice", open_invoice.name)
				payment_entry.mode_of_payment = mode_of_payment
				payment_entry.reference_no = open_invoice.customer + "/" + open_invoice.name
				payment_entry.reference_date = open_invoice.due_date
				payment_entry.insert()
				payment_entry.submit()
				frappe.db.commit()

		return "Success"
	except Exception as e:
		frappe.log_error(frappe.get_tracebeck(), "SEPA payments generation error")
		return "Error"

