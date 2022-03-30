# Copyright (c) 2019, Dokos SAS and Contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.email.doctype.notification.notification import get_context
from frappe.model.document import Document
from frappe.permissions import get_doctypes_with_read

from erpnext.accounts.general_ledger import make_entry, make_reverse_gl_entries


class AccountingJournal(Document):
	def validate(self):
		if self.conditions:
			self.validate_conditions()

	def validate_conditions(self):
		for condition in self.conditions:
			if condition.condition:
				temp_doc = frappe.new_doc(condition.document_type)
				try:
					frappe.safe_eval(condition.condition, None, get_context(temp_doc))
				except Exception:
					frappe.throw(_("The Condition '{0}' is invalid").format(condition))


@frappe.whitelist()
def get_entries(doctype, docnames):
	return frappe.get_list(
		"GL Entry",
		filters={
			"voucher_type": doctype,
			"voucher_no": ("in", frappe.parse_json(docnames)),
			"is_cancelled": 0,
		},
		fields=[
			"name",
			"account",
			"debit",
			"credit",
			"accounting_journal",
			"voucher_no",
			"account_currency",
		],
	)


@frappe.whitelist()
def accounting_journal_adjustment(doctype, docnames, accounting_journal):
	for docname in frappe.parse_json(docnames):
		original_entries = frappe.get_all(
			"GL Entry",
			fields=["*"],
			filters={"voucher_type": doctype, "voucher_no": docname, "is_cancelled": 0},
		)

		make_reverse_gl_entries(voucher_type=doctype, voucher_no=docname)

		for gl_entry in original_entries:
			gl_entry["name"] = None
			gl_entry["accounting_journal"] = accounting_journal
			make_entry(gl_entry, False, "Yes")
