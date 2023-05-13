# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.shipping_rule.shipping_rule import (
	FromGreaterThanToError,
	ManyBlankToValuesError,
	OverlappingConditionError,
)

test_records = frappe.get_test_records("Shipping Rule")


class TestShippingRule(FrappeTestCase):
	def test_from_greater_than_to(self):
		shipping_rule = frappe.copy_doc(test_records[0])
		shipping_rule.name = test_records[0].get("name")
		shipping_rule.get("conditions")[0].from_value = 101
		self.assertRaises(FromGreaterThanToError, shipping_rule.insert)

	def test_many_zero_to_values(self):
		shipping_rule = frappe.copy_doc(test_records[0])
		shipping_rule.name = test_records[0].get("name")
		shipping_rule.get("conditions")[0].to_value = 0
		self.assertRaises(ManyBlankToValuesError, shipping_rule.insert)

	def test_overlapping_conditions(self):
		for range_a, range_b in [
			((50, 150), (0, 100)),
			((50, 150), (100, 200)),
			((50, 150), (75, 125)),
			((50, 150), (25, 175)),
			((50, 150), (50, 150)),
		]:
			shipping_rule = frappe.copy_doc(test_records[0])
			shipping_rule.name = test_records[0].get("name")
			shipping_rule.get("conditions")[0].from_value = range_a[0]
			shipping_rule.get("conditions")[0].to_value = range_a[1]
			shipping_rule.get("conditions")[1].from_value = range_b[0]
			shipping_rule.get("conditions")[1].to_value = range_b[1]
			self.assertRaises(OverlappingConditionError, shipping_rule.insert)

	def test_with_taxes_on_shipping(self):
		frappe.get_doc(
			{
				"doctype": "Sales Taxes and Charges Template",
				"title": "_Test Tax for Shipping Rule",
				"company": "_Test Company",
				"taxes": [
					{
						# magically transforms into "On Previous Row Amount"
						"charge_type": "On Net Total",
						"account_head": "Sales Expenses - _TC",
						"cost_center": "Main - _TC",
						"description": "Shipping Tax",
						"rate": 20,
					}
				],
			}
		).insert()

		shipping_rule = frappe.copy_doc(test_records[0])
		shipping_rule.conditions = []
		shipping_rule.calculate_based_on = "Fixed"
		shipping_rule.shipping_amount = 10
		shipping_rule.label = "Fixed 1"
		shipping_rule.append("shipping_taxes", {"tax_template": "_Test Tax for Shipping Rule - _TC"})
		shipping_rule.name = None
		shipping_rule.insert()

		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": "_Test Company",
				"customer": "_Test Customer",
				"cost_center": "_Test Cost Center - _TC",
				"currency": "INR",
				"items": [
					{
						"item_code": "_Test Item",
						"qty": 1,
						"rate": 100,
						"warehouse": "_Test Warehouse - _TC",
						"cost_center": "_Test Cost Center - _TC",
					},
				],
				"shipping_rule": shipping_rule.name,
				"taxes_and_charges": "",
			}
		)
		si.insert()

		# 10.0 INR + 20% of 10.0 INR
		self.assertEqual(si.total_taxes_and_charges, 12.0)
		self.assertEqual(si.grand_total, 112.0)

	def test_custom_formula(self):
		shipping_rule = frappe.copy_doc(test_records[0])
		shipping_rule.conditions = []
		shipping_rule.calculate_based_on = "Custom Formula"
		shipping_rule.custom_formula = "doc.net_total * 0.1"
		shipping_rule.label = "Custom Formula 1"
		shipping_rule.name = None
		shipping_rule.insert()

		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": "_Test Company",
				"customer": "_Test Customer",
				"cost_center": "_Test Cost Center - _TC",
				"currency": "INR",
				"items": [
					{
						"item_code": "_Test Item",
						"qty": 1,
						"rate": 100,
						"warehouse": "_Test Warehouse - _TC",
						"cost_center": "_Test Cost Center - _TC",
					},
				],
				"shipping_rule": shipping_rule.name,
			}
		)
		si.insert()

		self.assertEqual(si.total_taxes_and_charges, 10.0)
		self.assertEqual(si.grand_total, 110.0)

	@unittest.skip("Not working yet.")
	def test_complex_custom_formula(self):
		shipping_rule = frappe.copy_doc(test_records[0])
		shipping_rule.conditions = []
		shipping_rule.calculate_based_on = "Custom Formula"
		shipping_rule.custom_formula = (
			"if doc.doctype == 'Sales Invoice':\n\treturn doc.net_total * 0.1\nreturn 1.23"
		)
		shipping_rule.label = "Custom Formula 2"
		shipping_rule.name = None
		shipping_rule.insert()

		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": "_Test Company",
				"customer": "_Test Customer",
				"cost_center": "_Test Cost Center - _TC",
				"currency": "INR",
				"items": [
					{
						"item_code": "_Test Item",
						"qty": 1,
						"rate": 100,
						"warehouse": "_Test Warehouse - _TC",
						"cost_center": "_Test Cost Center - _TC",
					},
				],
				"shipping_rule": shipping_rule.name,
			}
		)
		si.insert()

		self.assertEqual(si.total_taxes_and_charges, 10.0)
		self.assertEqual(si.grand_total, 110.0)


def create_shipping_rule(shipping_rule_type, shipping_rule_name):

	if frappe.db.exists("Shipping Rule", shipping_rule_name):
		return frappe.get_doc("Shipping Rule", shipping_rule_name)

	sr = frappe.new_doc("Shipping Rule")
	sr.account = "_Test Account Shipping Charges - _TC"
	sr.calculate_based_on = "Net Total"
	sr.company = "_Test Company"
	sr.cost_center = "_Test Cost Center - _TC"
	sr.label = shipping_rule_name
	sr.name = shipping_rule_name
	sr.shipping_rule_type = shipping_rule_type

	sr.append(
		"conditions",
		{
			"doctype": "Shipping Rule Condition",
			"from_value": 0,
			"parentfield": "conditions",
			"shipping_amount": 50.0,
			"to_value": 100,
		},
	)
	sr.append(
		"conditions",
		{
			"doctype": "Shipping Rule Condition",
			"from_value": 101,
			"parentfield": "conditions",
			"shipping_amount": 100.0,
			"to_value": 200,
		},
	)
	sr.append(
		"conditions",
		{
			"doctype": "Shipping Rule Condition",
			"from_value": 201,
			"parentfield": "conditions",
			"shipping_amount": 200.0,
			"to_value": 2000,
		},
	)
	sr.insert(ignore_permissions=True)
	sr.submit()
	return sr
