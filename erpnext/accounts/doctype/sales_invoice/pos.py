# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import json

import frappe
from frappe import _

from six import string_types

def get_root(table):
	root = frappe.db.sql(""" select name from `tab%(table)s` having
		min(lft)""" % {'table': table}, as_dict=1)

	return root[0].name


def update_multi_mode_option(doc, pos_profile):
	from frappe.model import default_fields

	if not pos_profile or not pos_profile.get('payments'):
		for payment in get_mode_of_payment(doc):
			payments = doc.append('payments', {})
			payments.mode_of_payment = payment.parent
			payments.account = payment.default_account
			payments.type = payment.type

		return

	for payment_mode in pos_profile.payments:
		payment_mode = payment_mode.as_dict()

		for fieldname in default_fields:
			if fieldname in payment_mode:
				del payment_mode[fieldname]

		doc.append('payments', payment_mode)


def get_items_list(pos_profile, company):
	cond = ""
	args_list = []
	if pos_profile.get('item_groups'):
		# Get items based on the item groups defined in the POS profile
		for d in pos_profile.get('item_groups'):
			args_list.extend([d.name for d in get_child_nodes('Item Group', d.item_group)])
		if args_list:
			cond = "and i.item_group in (%s)" % (', '.join(['%s'] * len(args_list)))

	return frappe.db.sql("""
		select
			i.name, i.item_code, i.item_name, i.description, i.item_group, i.has_batch_no,
			i.has_serial_no, i.is_stock_item, i.brand, i.stock_uom, i.image,
			id.expense_account, id.selling_cost_center, id.default_warehouse,
			i.sales_uom, c.conversion_factor
		from
			`tabItem` i
		left join `tabItem Default` id on id.parent = i.name and id.company = %s
		left join `tabUOM Conversion Detail` c on i.name = c.parent and i.sales_uom = c.uom
		where
			i.disabled = 0 and i.has_variants = 0 and i.is_sales_item = 1
			{cond}
		""".format(cond=cond), tuple([company] + args_list), as_dict=1)


def get_item_groups(pos_profile):
	item_group_dict = {}
	item_groups = frappe.db.sql("""Select name,
		lft, rgt from `tabItem Group` order by lft""", as_dict=1)

	for data in item_groups:
		item_group_dict[data.name] = [data.lft, data.rgt]
	return item_group_dict


def get_customers_list(pos_profile={}):
	cond = "1=1"
	customer_groups = []
	if pos_profile.get('customer_groups'):
		# Get customers based on the customer groups defined in the POS profile
		for d in pos_profile.get('customer_groups'):
			customer_groups.extend([d.name for d in get_child_nodes('Customer Group', d.customer_group)])
		cond = "customer_group in (%s)" % (', '.join(['%s'] * len(customer_groups)))

	return frappe.db.sql(""" select name, customer_name, customer_group,
		territory, customer_pos_id from tabCustomer where disabled = 0
		and {cond}""".format(cond=cond), tuple(customer_groups), as_dict=1) or {}


def get_customers_address(customers):
	customer_address = {}
	if isinstance(customers, string_types):
		customers = [frappe._dict({'name': customers})]

	for data in customers:
		address = frappe.db.sql(""" select name, address_line1, address_line2, city, state,
			email_id, phone, fax, pincode from `tabAddress` where is_primary_address =1 and name in
			(select parent from `tabDynamic Link` where link_doctype = 'Customer' and link_name = %s
			and parenttype = 'Address')""", data.name, as_dict=1)
		address_data = {}
		if address:
			address_data = address[0]

		address_data.update({'full_name': data.customer_name, 'customer_pos_id': data.customer_pos_id})
		customer_address[data.name] = address_data

	return customer_address


def get_contacts(customers):
	customer_contact = {}
	if isinstance(customers, string_types):
		customers = [frappe._dict({'name': customers})]

	for data in customers:
		contact = frappe.db.sql(""" select email_id, phone, mobile_no from `tabContact`
			where is_primary_contact =1 and name in
			(select parent from `tabDynamic Link` where link_doctype = 'Customer' and link_name = %s
			and parenttype = 'Contact')""", data.name, as_dict=1)
		if contact:
			customer_contact[data.name] = contact[0]

	return customer_contact


def get_child_nodes(group_type, root):
	lft, rgt = frappe.db.get_value(group_type, root, ["lft", "rgt"])
	return frappe.db.sql(""" Select name, lft, rgt from `tab{tab}` where
			lft >= {lft} and rgt <= {rgt} order by lft""".format(tab=group_type, lft=lft, rgt=rgt), as_dict=1)


def get_customer_group(data):
	if data.get('customer_group'):
		return data.get('customer_group')

	return frappe.db.get_single_value('Selling Settings', 'customer_group') or frappe.db.get_value('Customer Group', {'is_group': 0}, 'name')