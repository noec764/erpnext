# -*- coding: utf-8 -*-
# Copyright (c) 2021, Dokos SAS and contributors
# For license information, please see license.txt

import datetime
import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, add_days, month_diff, getdate, flt, add_to_date

ENTRYTYPES = {
	"Deferred charges": "Purchase Invoice",
	"Deferred income": "Sales Invoice"
}

ACCOUNTTYPE = {
	"Purchase Invoice": "expense_account",
	"Sales Invoice": "income_account"
}

class AdjustmentEntry(Document):
	pass

@frappe.whitelist()
def get_documents(entry_type, date, company):
	doctype = ENTRYTYPES.get(entry_type)

	if not doctype:
		return []

	account_type = ACCOUNTTYPE.get(doctype)

	documents = frappe.db.sql(f"""
		SELECT dt.name as document_name, dt.from_date, dt.to_date,
		'{doctype}' as document_type,
		it.{account_type} as account
		FROM `tab{doctype}` as dt
		LEFT JOIN `tab{doctype} Item` as it
		ON it.parent = dt.name
		WHERE dt.company={frappe.db.escape(company)}
		AND dt.from_date <= {frappe.db.escape(date)}
		AND dt.to_date > {frappe.db.escape(date)}
		AND dt.docstatus = 1
	""", as_dict=True)

	if not documents:
		return []

	documents = [frappe._dict(line) for line in {tuple(document.items()) for document in documents}]

	documents_list = ", ".join([f"'{x.document_name}'" for x in documents])
	account_list = ", ".join([f"'{x.account}'" for x in documents])

	gl_entries = frappe.db.sql(f"""
		SELECT account, debit, credit, voucher_type, voucher_no
		FROM `tabGL Entry`
		WHERE voucher_type='{doctype}'
		AND voucher_no in ({documents_list})
		AND account in ({account_list})
	""", as_dict=True)

	gl_by_document = {gl_entry.voucher_no: {} for gl_entry in gl_entries}
	for gl_entry in gl_entries:
		gl_by_document[gl_entry.voucher_no].update({
			gl_entry.account: (gl_entry.debit, gl_entry.credit)
		})

	for document in documents:
		debit = gl_by_document.get(document.document_name, {}).get(document.account, [0.0, 0.0])[0]
		credit = gl_by_document.get(document.document_name, {}).get(document.account, [0.0, 0.0])[1]
		net_amount = abs(debit - credit)
		document.update({
			"debit": debit,
			"credit": credit,
			"posting_amount": get_posting_amount(document.to_date, date, net_amount)
		})

	return documents

def get_posting_amount(to_date, date, net_amount):
	no_of_days = 0.0
	no_of_months = month_diff(to_date, add_days(date, 1))

	for month in range(no_of_months):
		if month + 1 == no_of_months:
			no_of_days += min(date_diff(to_date, datetime.date(getdate(to_date).year, getdate(to_date).month, 1)), 30)
		else:
			no_of_days += 30

	if no_of_days:
		posting_amount = flt(net_amount) * (flt(no_of_days) / 360)
		return posting_amount if posting_amount > 0.1 else 0.0
	else:
		return 0.0
