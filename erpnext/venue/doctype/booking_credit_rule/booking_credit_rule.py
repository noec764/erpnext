# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry

class BookingCreditRule(Document):
	def process_rule(self, doc):
		for condition in self.booking_credit_rules:
			if frappe.safe_eval(condition.condition, None, {"doc": doc}):
				if self.rule_type == "Booking Credits Addition":
					frappe.get_doc({
						"doctype": "Booking Credit",
						"date": doc.date,
						"customer": doc.customer,
						"quantity": condition.credit_qty,
						"uom": condition.credit_uom
					}).insert(ignore_permissions=True)
				else:
					frappe.get_doc({
						"doctype": "Booking Credit Usage",
						"date": doc.date,
						"customer": doc.customer,
						"quantity": condition.credit_qty,
						"uom": condition.credit_uom
					}).insert(ignore_permissions=True)


def trigger_credit_rules(doc, method):
	if doc.doctype in ("Sales Order", "Sales Invoice"):
		transaction_date = "posting_date" if doc.doctype == "Sales Invoice" else "transaction_date"
		for item in doc.items:
			rules = frappe.get_all("Booking Credit Rule", 
				filters={
					"rule_type": "Booking Credits Addition",
					"addition_trigger": f"{doc.doctype} Submission",
					"item": item.item_code
				})
			if rules:
				process_credit_rules(rules, frappe._dict({**doc.as_dict(), **item.as_dict(), **{"date": getattr(doc, transaction_date)}}))

	elif doc.doctype == "Item Booking":
		if doc.status == "Confirmed":
			rules = frappe.get_all("Booking Credit Rule", 
				filters={
					"rule_type": "Booking Credits Deduction",
					"deduction_trigger": "Item Booking Confirmation",
					"item": doc.item
				})
			if rules:
				process_credit_rules(rules, frappe._dict({**doc.as_dict(), **{"date": doc.starts_on}}))

def process_credit_rules(rules, doc):
	for rule in rules:
		frappe.get_doc("Booking Credit Rule", rule.name).process_rule(doc)