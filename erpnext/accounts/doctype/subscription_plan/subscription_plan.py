# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from erpnext.accounts.party import get_default_price_list
from erpnext.stock.get_item_details import get_price_list_rate_for
from erpnext.accounts.doctype.pricing_rule.pricing_rule import get_pricing_rule_for_item
from frappe.utils import nowdate

class SubscriptionPlan(Document):
	def validate(self):
		self.validate_interval_count()
		self.validate_gateway_plans()

	def validate_interval_count(self):
		if self.billing_interval_count < 1:
			frappe.throw(_('Billing Interval Count cannot be less than 1'))

	def validate_gateway_plans(self):
		for plan in self.payment_plans:
			gateway = frappe.get_doc("Payment Gateway", plan.payment_gateway)
			gateway.validate_subscription_plan(self.currency, plan.payment_plan)

@frappe.whitelist()
def get_plan_rate(company, customer, plan, quantity=1, date=nowdate()):
	plan = frappe.get_doc("Subscription Plan", plan)
	if plan.price_determination == "Fixed rate":
		return plan.cost

	elif plan.price_determination == "Based on price list":
		customer_doc = frappe.get_doc("Customer", customer)
		price_list = get_default_price_list(customer_doc)
		if not price_list:
			price_list = frappe.db.get_value("Price List", {"selling": 1})

		price_list_rate = get_price_list_rate_for({
			"company": company,
			"uom": plan.uom,
			"customer": customer,
			"price_list": price_list,
			"currency": plan.currency,
			"min_qty": quantity,
			"transaction_date": date
		}, plan.item)

		rule = get_pricing_rule_for_item(frappe._dict({
			"company": company,
			"uom": plan.uom,
			"item_code": plan.item,
			"stock_qty": quantity,
			"transaction_type": "selling",
			"price_list_rate": price_list_rate,
			"price_list_currency": frappe.db.get_value("Price List", price_list, "currency"),
			"price_list": price_list,
			"customer": customer,
			"currency": plan.currency,
			"transaction_date": date,
			"warehouse": frappe.db.get_value("Warehouse", dict(is_group=1, parent_warehouse=''))
		}))

		if rule.get("price_list_rate"):
			price_list_rate = rule.get("price_list_rate")

		return price_list_rate or 0
