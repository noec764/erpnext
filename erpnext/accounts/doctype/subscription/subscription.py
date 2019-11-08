# -*- coding: utf-8 -*-
# Copyright (c) 2019, Dokos SAS and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import nowdate, getdate, cint, add_days, date_diff, \
	get_last_day, add_to_date, flt, global_date_format, add_years, today
from erpnext.accounts.doctype.subscription_plan.subscription_plan import get_plan_rate
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
import numpy as np

class Subscription(Document):
	def onload(self):
		self.get_subscription_rates()

	def before_insert(self):
		self.update_subscription_period(self.start)

	def after_insert(self):
		self.set_subscription_status()

	def validate(self):
		self.get_subscription_rates()
		self.validate_trial_period()
		self.validate_plans_billing_cycle(self.get_billing_cycle_and_interval())
		self.validate_plans_pricing_rule()
		self.validate_subscription_period()
		self.simulate_grand_total_calculation()

	def on_update(self):
		self.set_subscription_status()
		self.update_payment_gateway_subscription()

	def update_subscription_period(self, date=None):
		self.set_current_invoice_start(date)
		self.set_current_invoice_end()

	def validate_subscription_period(self):
		if self.trial_period_start and getdate(self.trial_period_end) > getdate(self.current_invoice_start):
			if self.period_has_passed(self.trial_period_end):
				self.update_subscription_period(add_days(self.trial_period_end, 1))
		elif self.is_new_subscription():
			self.update_subscription_period(self.start)
		elif self.has_invoice_for_period():
			self.update_subscription_period(self.current_invoice_start)

		if self.cancel_at_period_end:
			self.cancel_subscription_at_period_end()

	def set_current_invoice_start(self, date=None):
		if self.trial_period_start and self.is_trial():
			self.current_invoice_start = self.trial_period_start
		elif date:
			self.current_invoice_start = date
		else:
			self.current_invoice_start = nowdate()

	def set_current_invoice_end(self):
		if self.trial_period_start and getdate(self.trial_period_end) > getdate(self.current_invoice_start):
			self.current_invoice_end = self.trial_period_end
		else:
			billing_cycle_info = self.get_billing_cycle_data()
			if billing_cycle_info:
				self.current_invoice_end = add_to_date(self.current_invoice_start, **billing_cycle_info)
			else:
				self.current_invoice_end = get_last_day(self.current_invoice_start)

	def process(self, from_gateway=False):
		if self.cancel_at_period_end:
			self.cancel_subscription_at_period_end()

		if self.cancellation_date and self.period_has_passed(add_days(self.cancellation_date, -1)):
			self.cancel_subscription()

		if self.status == 'Active':
			if not (self.payment_gateway_reference and self.payment_gateway_lifecycle) or from_gateway:
				self.process_active_subscription()
		elif self.status == 'Trial':
			self.set_subscription_status()

	def process_active_subscription(self):
		if self.trial_period_start and getdate(self.trial_period_end) >= getdate(self.current_invoice_end):
			self.update_subscription_period(add_days(self.trial_period_end, 1))
			self.save()

		elif not self.generate_invoice_at_period_start and self.period_has_passed(self.current_invoice_end):
			self.generate_sales_order()
			if not self.has_invoice_for_period():
				self.generate_invoice()
				self.update_subscription_period(add_days(self.current_invoice_end, 1))
				self.generate_sales_order()
			else:
				self.update_subscription_period(add_days(self.current_invoice_end, 1))
				self.generate_sales_order()
			self.save()

		elif self.generate_invoice_at_period_start:
			self.generate_sales_order()
			if self.has_invoice_for_period() and self.period_has_passed(self.current_invoice_end):
				self.update_subscription_period(add_days(self.current_invoice_end, 1))
				self.generate_sales_order()
				self.generate_invoice()
				self.save()

			elif not self.has_invoice_for_period() and self.period_has_passed(add_days(self.current_invoice_start, -1)):
				self.generate_invoice()

	@staticmethod
	def period_has_passed(end_date):
		if not end_date:
			return False

		end_date = getdate(end_date)
		return getdate(nowdate()) > getdate(end_date)

	@staticmethod
	def validate_plans_billing_cycle(billing_cycle_data):
		if billing_cycle_data and len(billing_cycle_data) != 1:
			frappe.throw(_('You can only have Plans with the same billing cycle in a Subscription'))

	def validate_plans_pricing_rule(self):
		rules = self.get_plans_pricing_rules()
		if len(rules) > 1:
			frappe.throw(_("Please select plans with the same price determination rule"))

	def get_plans_pricing_rules(self):
		rules = set()
		for plan in self.plans:
			rules.add(frappe.db.get_value("Subscription Plan", plan.plan, "price_determination"))

		return rules

	def get_billing_cycle_and_interval(self):
		plan_names = [plan.plan for plan in self.plans]
		billing_info = frappe.db.sql(
			'select distinct `billing_interval`, `billing_interval_count` '
			'from `tabSubscription Plan` '
			'where name in %s',
			(plan_names,), as_dict=1
		)

		return billing_info

	def get_billing_cycle_data(self):
		billing_info = self.get_billing_cycle_and_interval()

		self.validate_plans_billing_cycle(billing_info)

		if billing_info:
			data = dict()
			interval = billing_info[0]['billing_interval']
			interval_count = billing_info[0]['billing_interval_count']
			if interval not in ['Day', 'Week']:
				data['days'] = -1
			if interval == 'Day':
				data['days'] = interval_count - 1
			elif interval == 'Month':
				data['months'] = interval_count
			elif interval == 'Year':
				data['years'] = interval_count
			elif interval == 'Week':
				data['days'] = interval_count * 7 - 1

			return data

	def set_subscription_status(self):
		if self.is_trial() and self.status != 'Trial':
			self.db_set('status', 'Trial')
		elif self.status != 'Cancelled':
			self.db_set('status', 'Active')

		self.reload()

	def current_invoice_is_past_due(self, current_invoice=None):
		if not current_invoice:
			current_invoice = self.get_current_invoice()

		if not current_invoice:
			return False
		else:
			return getdate(nowdate()) > getdate(current_invoice.due_date)

	def get_current_invoice(self):
		current_invoices = self.get_current_documents("Sales Invoice")

		if current_invoices:
			validated_invoices = [x for x in current_invoices if x.get("docstatus") == 1]
			draft_invoices = [x for x in current_invoices if x.get("docstatus") == 0]
			if validated_invoices:
				current_invoice = validated_invoices[0].get("name")
			elif draft_invoices:
				current_invoice = draft_invoices[0].get("name")
			else:
				current_invoice = current_invoices[0].name

			return frappe.get_doc('Sales Invoice', current_invoice)

	def is_new_subscription(self):
		return False if frappe.get_all("Sales Invoice", filters={"subscription": self.name}) \
			else True

	def is_trial(self):
		if self.trial_period_start:
			return getdate(self.trial_period_end) > getdate(nowdate())
		else:
			return False

	def validate_trial_period(self):
		if self.trial_period_start and self.trial_period_end:
			if getdate(self.trial_period_end) < getdate(self.trial_period_start):
				frappe.throw(_('Trial Period End Date Cannot be before Trial Period Start Date'))

		elif self.trial_period_start and not self.trial_period_end:
			frappe.throw(_('Both Trial Period Start Date and Trial Period End Date must be set'))

	def generate_sales_order(self):
		if self.create_sales_order:
			if not self.has_sales_order_for_period() and self.period_has_passed(add_days(self.current_invoice_start, -1)):
				try:
					self.create_new_sales_order()
				except Exception:
					frappe.log_error(frappe.get_traceback(), _("Sales order generation error for subscription {0}").format(self.name))

	def create_new_sales_order(self):
		sales_order = frappe.new_doc('Sales Order')
		sales_order.flags.ignore_permissions = True
		sales_order.transaction_date = self.current_invoice_start
		sales_order.delivery_date = self.current_invoice_start if self.generate_invoice_at_period_start else self.current_invoice_end
		sales_order = self.set_subscription_invoicing_details(sales_order)

		sales_order.flags.ignore_mandatory = True
		sales_order.set_missing_values()
		sales_order.save()
		sales_order.submit()

		return sales_order

	def generate_invoice(self, prorate=0, simulate=False):
		try:
			return self.create_invoice(prorate, simulate)
		except Exception:
			frappe.log_error(frappe.get_traceback(), _("Invoice generation error for subscription {0}").format(self.name))

	def create_invoice(self, prorate, simulate=False):
		current_sales_order = self.get_current_documents("Sales Order")
		if current_sales_order:
			from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
			invoice = make_sales_invoice(current_sales_order[0], ignore_permissions=True)
			self.add_due_date(invoice)
			self.add_subscription_dates(invoice)

		else:
			invoice = frappe.new_doc('Sales Invoice')
			invoice.flags.ignore_permissions = True
			invoice = self.set_subscription_invoicing_details(invoice, prorate)

		invoice.set_posting_time = 1
		invoice.posting_date = self.current_invoice_start if self.generate_invoice_at_period_start else self.current_invoice_end
		invoice.posting_date = self.current_invoice_start if self.generate_invoice_at_period_start else self.current_invoice_end
		invoice.tax_id = frappe.db.get_value("Customer", invoice.customer, "tax_id")

		## Add dimensions in invoice for subscription:
		accounting_dimensions = get_accounting_dimensions()

		for dimension in accounting_dimensions:
			if self.get(dimension):
				invoice.update({
					dimension: self.get(dimension)
				})

		invoice.flags.ignore_mandatory = True
		invoice.set_missing_values()
		if not simulate:
			invoice.save()

			if self.submit_invoice:
				invoice.submit()

		return invoice

	def set_subscription_invoicing_details(self, document, prorate=0):
		document.customer = self.customer
		document.set_missing_lead_customer_details()
		document.subscription = self.name
		document.ignore_pricing_rule = 1 if self.get_plans_pricing_rules().pop() == "Fixed rate" else 0

		# Subscription is better suited for service items. It won't update `update_stock`
		# for that reason
		items_list = self.get_items_from_plans(self.plans,\
			document.posting_date if document.doctype == "Sales Invoice" else document.transaction_date, prorate)
		for item in items_list:
			document.append('items', item)

		# Shipping
		if self.shipping_rule:
			document.shipping_rule = self.shipping_rule
			document.apply_shipping_rule()

		# Taxes
		if self.tax_template:
			document.taxes_and_charges = self.tax_template
		else:
			from erpnext.accounts.party import set_taxes
			document.taxes_and_charges = set_taxes(
				party=self.customer,
				party_type="Customer",
				posting_date=document.posting_date if document.doctype == "Sales Invoice" else document.transaction_date,
				company=self.company,
				customer_group=frappe.db.get_value("Customer", self.customer, "customer_group"),
				tax_category=document.tax_category,
				billing_address=document.customer_address,
				shipping_address=document.shipping_address_name
			)
		document.set_taxes()

		self.add_due_date(document)

		# Discounts
		if self.additional_discount_percentage:
			document.additional_discount_percentage = self.additional_discount_percentage

		if self.additional_discount_amount:
			document.discount_amount = self.additional_discount_amount

		if self.additional_discount_percentage or self.additional_discount_amount:
			discount_on = self.apply_additional_discount
			document.apply_additional_discount = discount_on if discount_on else 'Grand Total'

		self.add_subscription_dates(document)

		# Terms and conditions
		if self.terms_and_conditions:
			from erpnext.setup.doctype.terms_and_conditions.terms_and_conditions import get_terms_and_conditions
			document.tc_name = self.terms_and_conditions
			document.terms = get_terms_and_conditions(self.terms_and_conditions, document.__dict__)

		return document

	def add_due_date(self, document):
		document.append(
			'payment_schedule',
			{
				'due_date': add_days(self.current_invoice_start if \
					self.generate_invoice_at_period_start else self.current_invoice_end, cint(self.days_until_due)),
				'invoice_portion': 100
			}
		)

	def add_subscription_dates(self, document):
		# Subscription period
		document.from_date = self.current_invoice_start
		document.to_date = self.current_invoice_end

	def get_items_from_plans(self, plans, date, prorate=0):
		if prorate:
			prorata_factor = self.get_prorata_factor()

		items = []
		for plan in plans:
			item_code = frappe.db.get_value("Subscription Plan", plan.plan, "item")
			if not prorate:
				items.append({'item_code': item_code, 'qty': plan.qty, \
					'rate': get_plan_rate(self.company, self.customer, plan.plan, plan.qty, getdate(date)),\
					'description': plan.description})
			else:
				items.append({'item_code': item_code, 'qty': plan.qty, \
					'rate': (get_plan_rate(self.company, self.customer, plan.plan, plan.qty, getdate(date)) * prorata_factor),\
					'description': plan.description})

		return items

	def cancel_subscription_at_period_end(self):
		if not self.cancellation_date:
			self.cancellation_date = self.current_invoice_end
			self.save()

	def has_invoice_for_period(self):
		return True if self.get_current_documents("Sales Invoice") else False

	def has_sales_order_for_period(self):
		return True if self.get_current_documents("Sales Order") else False

	def get_current_documents(self, doctype):
		period_documents = []

		transaction_date = "posting_date" if doctype == "Sales Invoice" else "transaction_date"

		billing_cycle_info = self.get_billing_cycle_data()
		documents = frappe.get_all(doctype, filters={"subscription": self.name}, \
			fields=[transaction_date, "name", "docstatus"])
		for document in documents:
			if billing_cycle_info:
				calculated_end = add_to_date(document.get(transaction_date), **billing_cycle_info)
			else:
				calculated_end = get_last_day(document.get(transaction_date))

			if calculated_end >= getdate(self.current_invoice_end):
				period_documents.append(document)

		return period_documents

	def cancel_subscription(self):
		if self.status != 'Cancelled':
			generate_invoice = True if self.status == 'Active' else False
			self.status = 'Cancelled'
			if not self.cancellation_date:
				self.cancellation_date = self.current_invoice_end

			if generate_invoice and not self.generate_invoice_at_period_start \
				and not (self.payment_gateway_reference and self.payment_gateway_lifecycle):
				self.generate_invoice(prorate=self.prorate_invoice)

			self.save()

			self.cancel_gateway_subscription()

	def cancel_gateway_subscription(self):
		if self.payment_gateway and self.payment_gateway_reference:
			gateway_settings, gateway_controller = frappe.db.get_value("Payment Gateway", \
				self.payment_gateway, ["gateway_settings", "gateway_controller"])
			settings = frappe.get_doc(gateway_settings, gateway_controller)
			if hasattr(settings, "cancel_subscription"):
				settings.cancel_subscription(**{
					"subscription": self.payment_gateway_reference,
					"prorate": True if self.prorate_invoice else False
				})

	def restart_subscription(self):
		if self.status == 'Cancelled':
			self.status = 'Active'
			self.cancellation_date = None
			self.cancel_at_period_end = 0
			self.prorate_invoice = 0
			self.update_subscription_period(nowdate())
			self.save()
		else:
			frappe.throw(_('You cannot restart a Subscription that is not cancelled.'))

	def get_precision(self):
		invoice = self.get_current_invoice()
		if invoice:
			return invoice.precision('grand_total')


	def get_prorata_factor(self):
		consumed = flt(date_diff(self.cancellation_date, self.current_invoice_start) + 1)
		plan_days = flt(date_diff(self.current_invoice_end, self.current_invoice_start) + 1)
		prorata_factor = consumed / plan_days

		return prorata_factor

	def get_subscription_rates(self):
		total = 0
		for plan in self.plans:
			plan.rate = get_plan_rate(self.company, self.customer, plan.plan, plan.qty)
			total += (flt(plan.qty) * flt(plan.rate))

		if total != self.total:
			self.total = total

	def simulate_grand_total_calculation(self):
		self.grand_total = self.simulated_grand_total()

	def simulated_grand_total(self):
		invoice = self.generate_invoice(simulate=True)
		invoice._action = "save"
		invoice.run_method("validate")
		return invoice.grand_total

	def update_payment_gateway_subscription(self):
		if self.payment_gateway:
			settings, controller = frappe.db.get_value("Payment Gateway", self.payment_gateway, ["gateway_settings", "gateway_controller"])
			if settings and controller:
				gateway_settings = frappe.get_doc(settings, controller)

				if hasattr(gateway_settings, 'on_subscription_update'):
					gateway_settings.run_method('on_subscription_update', self)

def update_grand_total():
	subscriptions = frappe.get_all("Subscription", filters={"status": ("!=", "Cancelled")}, \
		fields=["name", "grand_total"])
	for subscription in subscriptions:
		sub = frappe.get_doc("Subscription", subscription.get("name"))
		simulated_total = sub.run_method("simulated_grand_total")

		if simulated_total != subscription.get("grand_total"):
			sub.run_method("simulate_grand_total_calculation")
			sub.save()

def process_all():
	subscriptions = frappe.get_all("Subscription", filters={"status": ("!=", "Cancelled")})
	for subscription in subscriptions:
		process(subscription)

def process(data, date=None):
	if data:
		try:
			subscription = frappe.get_doc('Subscription', data['name'])
			subscription.process()
		except frappe.ValidationError:
			frappe.db.rollback()
			frappe.db.begin()
			frappe.log_error(frappe.get_traceback())
			frappe.db.commit()

@frappe.whitelist()
def cancel_subscription(**kwargs):
	subscription = frappe.get_doc('Subscription', kwargs.get("name"))
	subscription.cancellation_date = kwargs.get("cancellation_date")
	subscription.prorate_invoice = kwargs.get("prorate_invoice")
	subscription.save()


@frappe.whitelist()
def restart_subscription(name):
	subscription = frappe.get_doc('Subscription', name)
	subscription.restart_subscription()

@frappe.whitelist()
def get_subscription_updates(name):
	subscription = frappe.get_doc('Subscription', name)
	subscription.process()

@frappe.whitelist()
def get_chart_data(title, doctype, docname):
	invoices = frappe.get_all("Sales Invoice", filters={"subscription": docname,}, \
		fields=["name", "outstanding_amount", "grand_total", "posting_date", "currency"], group_by="posting_date")

	if len(invoices) < 1:
		return {}

	symbol = frappe.db.get_value("Currency", invoices[0].currency, "symbol", cache=True) \
		or invoices[0].currency

	dates = []
	total = []
	outstanding = []
	for invoice in invoices[:20]:
		dates.insert(0, invoice.posting_date)
		total.insert(0, invoice.grand_total)
		outstanding.insert(0, invoice.outstanding_amount)

	mean_value = np.mean(np.array([x.grand_total for x in invoices]))

	data = {
		'title': title + " (" + symbol + ")",
		'data': {
			'datasets': [
				{
					'name': _("Invoiced"),
					'values': total
				},
				{
					'name': _("Outstanding Amount"),
					'values': outstanding
				}
			],
			'labels': dates,
			'yMarkers': [
				{
					'label': _("Average invoicing"),
					'value': mean_value,
					'options': {
						'labelPos': 'left'
						}
				}
			]
		},
		'type': 'bar',
		'colors': ['green', 'orange']
	}

	return data

@frappe.whitelist()
def subscription_headline(name):
	subscription = frappe.get_doc('Subscription', name)

	billing_cycle_info = subscription.get_billing_cycle_data()

	if not subscription.has_invoice_for_period():
		if subscription.generate_invoice_at_period_start:
			if subscription.is_trial():
				next_invoice_date = add_days(subscription.trial_period_end, 1)
			else:
				next_invoice_date = subscription.current_invoice_start
		else:
			if subscription.is_trial():
				if billing_cycle_info:
					next_invoice_date = add_to_date(add_days(subscription.trial_period_end, 1), \
						**billing_cycle_info)
				else:
					next_invoice_date = get_last_day(add_days(subscription.trial_period_end, 1))
			else:
				next_invoice_date = add_days(subscription.current_invoice_end, 1)

	else:
		if subscription.generate_invoice_at_period_start:
			next_invoice_date = add_days(subscription.current_invoice_end, 1)
		else:
			if billing_cycle_info:
				next_invoice_date = add_to_date(add_days(subscription.current_invoice_end, 1), \
					**billing_cycle_info)
			else:
				next_invoice_date = get_last_day(add_days(subscription.current_invoice_end, 1))

	if subscription.cancel_at_period_end and getdate(nowdate()) \
		> getdate(subscription.current_invoice_end):
		return _("This subscription will be cancelled on {0}").format(\
			global_date_format(next_invoice_date))

	return _("The next invoice will be generated on {0}").format(global_date_format(next_invoice_date))
