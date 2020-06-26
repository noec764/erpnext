# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
import os
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup(company=None, patch=True):
	if not patch:
		make_custom_fields()
		add_custom_roles_for_reports()

def make_custom_fields():
	custom_fields = {
		'Company': [
			dict(fieldname='siren_number', label='SIREN Number',
			fieldtype='Data', insert_after='website')
		],
		'Account': [
			dict(fieldname='negative_in_balance_sheet', label='Negative in Balance Sheet',
			fieldtype='Check', insert_after='include_in_gross', depends_on='eval:doc.report_type=="Balance Sheet" && !doc.is_group',
			description='Balance is debit for asset or credit for liability accounts')
			dict(fieldname='balance_sheet_alternative_category', label='Balance Sheet Other Category',
			fieldtype='Link', options='Account', insert_after='negative_in_balance_sheet', depends_on='eval:doc.report_type=="Balance Sheet" && !doc.is_group')
		]
	}

	create_custom_fields(custom_fields, ignore_validate=True)

def add_custom_roles_for_reports():
	report_name = 'Fichier des Ecritures Comptables [FEC]'

	if not frappe.db.get_value('Custom Role', dict(report=report_name)):
		frappe.get_doc(dict(
			doctype='Custom Role',
			report=report_name,
			roles= [
				dict(role='Accounts Manager')
			]
		)).insert()
