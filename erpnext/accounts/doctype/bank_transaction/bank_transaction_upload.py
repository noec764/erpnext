# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import json
from frappe.utils import getdate, flt
from frappe.utils.dateutils import parse_date
from six import iteritems
from ofxtools.Parser import OFXTree

@frappe.whitelist()
def upload_csv_bank_statement():
	if frappe.safe_encode(frappe.local.uploaded_filename).lower().endswith("csv".encode('utf-8')):
		from frappe.utils.csvutils import read_csv_content
		rows = read_csv_content(frappe.local.uploaded_file)

	elif frappe.safe_encode(frappe.local.uploaded_filename).lower().endswith("xlsx".encode('utf-8')):
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file
		rows = read_xlsx_file_from_attached_file(fcontent=frappe.local.uploaded_file)

	elif frappe.safe_encode(frappe.local.uploaded_filename).lower().endswith("xls".encode('utf-8')):
		from frappe.utils.xlsxutils import read_xls_file_from_attached_file
		rows = read_xls_file_from_attached_file(frappe.local.uploaded_file)

	else:
		frappe.throw(_("Please upload a csv, xls or xlsx file"))

	columns = [{"name": x, "content": x} for x in rows[0]]
	rows.pop(0)
	data = rows
	return {"columns": columns, "data": data}

@frappe.whitelist()
def upload_ofx_bank_statement():
	parser = OFXTree()
	columns = [
		{
			"name": "id",
			"content": "ID"
		},
		{
			"name": "type",
			"content": _("Type")
		},
		{
			"name": "date",
			"content": _("Date")
		},
		{
			"name": "description",
			"content": _("Description")
		},
		{
			"name": "debit",
			"content": _("Debit")
		},
		{
			"name": "credit",
			"content": _("Credit")
		}
	]
	data = []
	try:
		from io import BytesIO
		import pandas as pd
		with BytesIO(frappe.local.uploaded_file) as file:
			parser.parse(file)
			ofx = parser.convert()
			stmts = ofx.statements
			print(stmts[0].account)
			for stmt in stmts:
				txs = stmt.transactions
				for tx in txs:
					data.append(make_transaction_row(tx))

		return {"columns": columns, "data": data}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("OFX Parser Error"))

def make_transaction_row(transaction):
	return [
		transaction.fitid,
		transaction.trntype,
		getdate(transaction.dtposted),
		transaction.name + " | " + transaction.memo,
		abs(transaction.trnamt) if flt(transaction.trnamt) < 0 else 0,
		transaction.trnamt if flt(transaction.trnamt) > 0 else 0
	]

@frappe.whitelist()
def create_bank_entries(columns, data, bank_account, upload_type=None):
	if not upload_type:
		frappe.throw(_("Please upload a file first"))

	header_map = get_header_mapping(columns, bank_account, upload_type)

	success = 0
	errors = 0
	duplicates = 0
	for d in json.loads(data):
		if all(item is None for item in d) is True:
			continue
		fields = {}
		for key, value in iteritems(header_map):
			fields.update({key: d[int(value)-1]})

		try:
			bank_transaction = frappe.new_doc("Bank Transaction")
			bank_transaction.update(fields)
			bank_transaction.date = getdate(parse_date(bank_transaction.date))
			bank_transaction.bank_account = bank_account
			bank_transaction.flags.import_statement = True
			bank_transaction.insert()
			bank_transaction.submit()
			success += 1
			frappe.db.commit()
		except frappe.UniqueValidationError:
			duplicates += 1
			frappe.clear_messages()

		except frappe.DuplicateEntryError:
			duplicates += 1
			frappe.clear_messages()

		except Exception:
			errors += 1
			frappe.log_error(frappe.get_traceback(), _("Bank transaction creation error"))

	return {"success": success, "errors": errors, "duplicates": duplicates}

def get_header_mapping(columns, bank_account, upload_type):
	if upload_type == 'csv':
		return get_csv_header_mapping(columns, bank_account)
	elif upload_type == 'ofx':
		return get_ofx_header_mapping(columns)

def get_csv_header_mapping(columns, bank_account):
	mapping = get_bank_mapping(bank_account)
	return header_mapping(columns, mapping)

def get_ofx_header_mapping(columns):
	mapping = {
		"id": "reference_number",
		"date": "date",
		"description": "description",
		"debit": "debit",
		"credit": "credit"
	}

	return header_mapping(columns, mapping)

def get_bank_mapping(bank_account):
	bank_name = frappe.db.get_value("Bank Account", bank_account, "bank")
	bank = frappe.get_doc("Bank", bank_name)

	mapping = {row.file_field:row.bank_transaction_field for row in bank.bank_transaction_mapping}

	return mapping

def header_mapping(columns, mapping):
	header_map = {}
	for column in json.loads(columns):
		if column.get("name") in mapping:
			header_map.update({mapping[column["name"]]: column["colIndex"]})

	return header_map
