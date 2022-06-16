# Copyright (c) 2021, Dokos SAS and Contributors
# For license information, please see license.txt

import copy

import frappe
import numpy as np
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import add_days, cint, flt, getdate, global_date_format, nowdate

from erpnext.accounts.doctype.subscription.subscription_plans_manager import (
	SubscriptionPlansManager,
)
from erpnext.accounts.doctype.subscription.subscription_state_manager import (
	SubscriptionPeriod,
	SubscriptionStateManager,
)
from erpnext.accounts.doctype.subscription.subscription_transaction import (
	SubscriptionInvoiceGenerator,
	SubscriptionPaymentEntryGenerator,
	SubscriptionPaymentRequestGenerator,
	SubscriptionSalesOrderGenerator,
)
from erpnext.accounts.party import get_default_contact

BILLING_STATUS = ["Billable", "Billing failed", "Cancelled and billable"]


class Subscription(Document):
	def onload(self):
		SubscriptionPlansManager(self).set_plans_rates()

	def validate(self):
		self.get_billing_contact()
		self.validate_interval_count()
		self.validate_trial_period()
		SubscriptionPlansManager(self).set_plans_status()
		SubscriptionPlansManager(self).set_plans_rates()
		self.calculate_total()
		self.calculate_grand_total()
		self.calculate_discounts()

	def on_update(self):
		self.update_payment_gateway_subscription()
		self.set_customer_status()

	def on_trash(self):
		events = frappe.get_all(
			"Subscription Event", filters={"subscription": self.name}, fields=["name", "docstatus"]
		)
		for event in events:
			if event.docstatus == 1:
				e = frappe.get_doc("Subscription Event", event.name)
				e.flags.ignore_permissions = True
				e.cancel()

			frappe.delete_doc("Subscription Event", event.name, force=True)

	def validate_interval_count(self):
		if self.billing_interval_count < 1:
			frappe.throw(_("Billing Interval Count cannot be less than 1"))

	def validate_trial_period(self):
		if self.trial_period_start and self.trial_period_end:
			if getdate(self.trial_period_end) < getdate(self.trial_period_start):
				frappe.throw(_("Trial Period End Date Cannot be before Trial Period Start Date"))

		elif self.trial_period_start and not self.trial_period_end:
			frappe.throw(_("Both Trial Period Start Date and Trial Period End Date must be set"))

	def calculate_total(self):
		self.total = SubscriptionPlansManager(self).get_plans_total()

	def calculate_grand_total(self):
		self.grand_total = SubscriptionInvoiceGenerator(self).get_simulation()

	def calculate_discounts(self):
		if self.apply_additional_discount:
			total = self.total if self.apply_additional_discount == "Net Total" else self.grand_total
			if self.additional_discount_percentage:
				self.additional_discount_amount = flt(total) * flt(self.additional_discount_percentage) / 100.0
			elif self.additional_discount_amount:
				self.additional_discount_percentage = flt(self.additional_discount_amount) / flt(total) * 100.0

	def process(self):
		SubscriptionPeriod(self).validate()
		SubscriptionPlansManager(self).set_plans_status()
		SubscriptionPlansManager(self).set_plans_rates()
		SubscriptionStateManager(self).set_status()

		if self.status in BILLING_STATUS:
			self.process_active_subscription()
			SubscriptionStateManager(self).set_status()
		elif self.status == "To order":
			self.generate_sales_order()
			SubscriptionStateManager(self).set_status()

		self.set_customer_status()

	def process_active_subscription(self):
		try:
			self.generate_sales_order()
			invoice = self.generate_invoice()
			SubscriptionStateManager(self).set_status()
			SubscriptionPaymentRequestGenerator(self, invoice.name).make_payment_request()
		except Exception:
			frappe.log_error(_("Subscription update error for subscription {0}").format(self.name))

	def generate_sales_order(self):
		if self.create_sales_order:
			return SubscriptionSalesOrderGenerator(self).create_new_sales_order()

	def generate_invoice(self):
		try:
			invoice = SubscriptionInvoiceGenerator(self).create_invoice()
			invoice.save()
			if self.submit_invoice:
				invoice.submit()
			return invoice
		except Exception:
			previous_status = self.status
			self.db_set("status", "Billing failed")
			self.add_subscription_event(
				"Status updated", **{"previous_status": previous_status, "new_status": "Billing failed"}
			)
			self.reload()
			frappe.throw(_("Invoicing error for subscription {0}").format(self.name))

	def cancel_subscription(self, **kwargs):
		self.cancellation_date = kwargs.get("cancellation_date") or self.current_invoice_end
		self.prorate_last_invoice = kwargs.get("prorate_last_invoice")
		self.save(ignore_permissions=kwargs.get("ignore_permissions"))
		self.cancel_gateway_subscription()

	def restart_subscription(self):
		self.status = "Active"
		self.current_invoice_start = (
			add_days(self.cancellation_date, 1) if self.cancellation_date else nowdate()
		)
		self.cancellation_date = None
		self.prorate_last_invoice = 0
		self.save()

	def cancel_gateway_subscription(self):
		if self.payment_gateway and self.payment_gateway_reference:
			gateway_settings, gateway_controller = frappe.db.get_value(
				"Payment Gateway", self.payment_gateway, ["gateway_settings", "gateway_controller"]
			)
			settings = frappe.get_doc(gateway_settings, gateway_controller)
			if hasattr(settings, "cancel_subscription"):
				settings.cancel_subscription(
					**{
						"subscription": self.payment_gateway_reference,
						"prorate": True if self.prorate_last_invoice else False,
					}
				)

	def update_payment_gateway_subscription(self):
		if self.payment_gateway and self.payment_gateway_reference:
			settings, controller = frappe.db.get_value(
				"Payment Gateway", self.payment_gateway, ["gateway_settings", "gateway_controller"]
			)
			if settings and controller:
				gateway_settings = frappe.get_doc(settings, controller)

				if hasattr(gateway_settings, "on_subscription_update"):
					gateway_settings.run_method("on_subscription_update", self)

	def add_subscription_event(self, event_type, **kwargs):
		if self.name:
			doc = frappe.get_doc(
				dict(
					{
						"doctype": "Subscription Event",
						"subscription": self.name,
						"date": nowdate(),
						"event_type": event_type,
						"period_start": self.current_invoice_start,
						"period_end": self.current_invoice_end,
					},
					**kwargs
				)
			)
			doc.flags.ignore_permissions = True
			doc.insert()
			doc.submit()

	def add_plan(self, plan):
		plan_doc = frappe.get_doc("Subscription Plan", plan)
		for plan_line in plan_doc.subscription_plans_template:
			line = copy.deepcopy(plan_line)
			self.append("plans", dict(line.as_dict(), **{"from_date": nowdate(), "name": None}))

	def remove_plan(self, line):
		for plan_line in self.plans:
			if plan_line.name == line:
				plan_line.to_date = nowdate()

	@frappe.whitelist()
	def create_stripe_invoice_item(self, plan_details):
		from erpnext.erpnext_integrations.doctype.stripe_settings.api import StripeInvoiceItem

		plan = frappe.parse_json(plan_details)

		if not plan.get("description") or not frappe.utils.strip_html_tags(plan.get("description")):
			frappe.throw(_("Please enter a description before creating an invoice item."))

		rate = cint(flt(SubscriptionPlansManager(self).get_plan_rate(plan)) * plan.qty * 100)

		if self.payment_gateway:
			gateway_settings, gateway_controller = frappe.db.get_value(
				"Payment Gateway", self.payment_gateway, ["gateway_settings", "gateway_controller"]
			)
			if gateway_settings == "Stripe Settings":
				stripe_settings = frappe.get_doc("Stripe Settings", gateway_controller)
				customer = frappe.db.get_value(
					"Integration References", dict(customer=self.customer), "stripe_customer_id"
				)
				return StripeInvoiceItem(stripe_settings).create(
					customer,
					amount=rate,
					currency=self.currency,
					description=frappe.utils.strip_html_tags(plan.get("description")),
					metadata={"reference_doctype": self.doctype, "reference_name": self.name},
				)

		frappe.msgprint(
			_(
				"The invoice item creation has failed. Check that this subscription is linked to a Stripe gateway."
			)
		)

	def update_outstanding(self):
		outstanding = sum(
			[
				x.outstanding_amount
				for x in frappe.get_all(
					"Sales Invoice",
					filters={"subscription": self.name, "docstatus": 1},
					fields=["outstanding_amount"],
				)
			]
		)
		self.db_set("outstanding_amount", outstanding)
		SubscriptionStateManager(self).set_status()

	def get_references_for_payment_request(self, payment_request):
		payment_request_period = frappe.db.get_value(
			"Subscription Event",
			dict(
				event_type="Payment request created",
				subscription=self.name,
				document_type="Payment Request",
				document_name=payment_request,
			),
			["period_start", "period_end"],
			as_dict=True,
		)

		if payment_request_period:
			return [
				{
					"reference_doctype": "Sales Invoice",
					"reference_name": x.name,
					"outstanding_amount": x.outstanding_amount,
				}
				for x in SubscriptionPeriod(
					self, start=payment_request_period.period_start, end=payment_request_period.period_end
				).get_current_documents("Sales Invoice")
				if x.docstatus == 1 and x.outstanding_amount > 0
			]

		return []

	def get_payment_request_for_period(self, start, end):
		return frappe.db.get_value(
			"Subscription Event",
			dict(
				event_type="Payment request created",
				subscription=self.name,
				document_type="Payment Request",
				period_start=start,
				period_end=end,
			),
			"document_name",
		) or frappe.db.get_value(
			"Subscription Event",
			dict(
				event_type="Payment request created",
				subscription=self.name,
				document_type="Payment Request",
				period_start=("<=", start),
				period_end=(">=", end),
			),
			"document_name",
		)

	def get_next_invoice_date(self):
		return SubscriptionPeriod(self).get_next_invoice_date()

	def create_payment(self):
		return SubscriptionPaymentEntryGenerator(self).create_payment()

	def create_payment_request(self):
		return SubscriptionPaymentRequestGenerator(self).create_payment_request()

	@frappe.whitelist()
	def link_sales_invoice(self, sales_invoice):
		frappe.db.set_value("Sales Invoice", sales_invoice, "subscription", self.name)

	def set_customer_status(self):
		frappe.get_doc("Customer", self.customer).set_status(update=True)

	def get_billing_contact(self):
		if self.customer and not self.contact_person:
			self.contact_person = get_default_contact("Customer", self.customer)


def update_grand_total():
	subscriptions = frappe.get_all(
		"Subscription", filters={"status": ("!=", "Cancelled")}, fields=["name", "grand_total"]
	)
	for subscription in subscriptions:
		sub = frappe.get_doc("Subscription", subscription.get("name"))
		previous_total = sub.total
		previous_grand_total = sub.grand_total
		sub.run_method("calculate_total")
		sub.run_method("calculate_grand_total")
		sub.run_method("calculate_discounts")
		if previous_total != sub.total or previous_grand_total != sub.grand_total:
			sub.save()


def process_all():
	subscriptions = frappe.get_all("Subscription", filters={"status": ("!=", "Cancelled")})
	for subscription in subscriptions:
		subscription = frappe.get_doc("Subscription", subscription.name)
		subscription.process()
		frappe.db.commit()


@frappe.whitelist()
def cancel_subscription(**kwargs):
	subscription = frappe.get_doc("Subscription", kwargs.get("name"))
	subscription.cancel_subscription(**kwargs)


@frappe.whitelist()
def restart_subscription(name):
	subscription = frappe.get_doc("Subscription", name)
	subscription.restart_subscription()


@frappe.whitelist()
def get_subscription_updates(name):
	subscription = frappe.get_doc("Subscription", name)
	subscription.process()
	frappe.db.commit()


@frappe.whitelist()
def get_payment_entry(name):
	subscription = frappe.get_doc("Subscription", name)
	return SubscriptionPaymentEntryGenerator(subscription).create_payment()


@frappe.whitelist()
def get_payment_request(name):
	subscription = frappe.get_doc("Subscription", name)
	return SubscriptionPaymentRequestGenerator(subscription).create_payment_request()


@frappe.whitelist()
def get_subscription_plan(plan):
	plan = frappe.get_doc("Subscription Plan", plan)
	meta = frappe.get_meta("Subscription Plan Detail")
	fields = [
		f.fieldname
		for f in meta.fields
		if f.fieldtype not in ("Section Break", "Column Break", "Button")
	]
	return [{f: p.get(f) for f in fields} for p in plan.subscription_plans_template]


@frappe.whitelist()
def get_chart_data(title, doctype, docname):
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"subscription": docname, "docstatus": 1},
		fields=["name", "outstanding_amount", "grand_total", "posting_date", "currency"],
		group_by="posting_date DESC",
		limit=20,
	)

	if len(invoices) < 1:
		return {}

	symbol = (
		frappe.db.get_value("Currency", invoices[0].currency, "symbol", cache=True)
		or invoices[0].currency
	)

	dates = []
	total = []
	outstanding = []
	for invoice in invoices:
		dates.insert(0, invoice.posting_date)
		total.insert(0, invoice.grand_total)
		outstanding.insert(0, invoice.outstanding_amount)

	mean_value = np.mean(np.array([x.grand_total for x in invoices]))

	data = {
		"title": title + " (" + symbol + ")",
		"data": {
			"datasets": [
				{"name": _("Invoiced"), "values": total},
				{"name": _("Outstanding Amount"), "values": outstanding},
			],
			"labels": dates,
			"yMarkers": [
				{"label": _("Average invoicing"), "value": mean_value, "options": {"labelPos": "left"}}
			],
		},
		"type": "bar",
		"colors": ["green", "orange"],
	}

	return data


@frappe.whitelist()
def subscription_headline(name):
	subscription = frappe.get_doc("Subscription", name)

	if subscription.cancellation_date and getdate(subscription.cancellation_date) > getdate(
		nowdate()
	):
		return _("This subscription will be cancelled on {0}").format(
			global_date_format(subscription.cancellation_date)
		)
	elif subscription.cancellation_date and subscription.cancellation_date <= getdate(nowdate()):
		return _("This subscription has been cancelled on {0}").format(
			global_date_format(subscription.cancellation_date)
		)
	elif not subscription.status:
		return _(
			"This subscription is not active yet.<br>You can activate it by clicking on 'Fetch Subscription Updates' or wait until the next automatic update (once an hour)."
		)

	next_invoice_date = SubscriptionPeriod(subscription).get_next_invoice_date()
	return (
		_("The next invoice will be generated on {0}").format(global_date_format(next_invoice_date))
		if next_invoice_date
		else ""
	)


@frappe.whitelist()
def new_invoice_end(subscription, end_date):
	new_date = getdate(end_date)
	doc = frappe.get_doc("Subscription", subscription)

	doc.current_invoice_end = new_date
	doc.add_subscription_event("New period")
	doc.save()


def get_list_context(context=None):
	templates = frappe.get_all(
		"Subscription Template",
		filters={"enable_on_portal": 1},
		fields=["name", "portal_description", "portal_image"],
	)
	context.update(
		{
			"show_sidebar": True,
			"show_search": True,
			"no_breadcrumbs": True,
			"title": _("Subscriptions"),
			"get_list": get_subscriptions_list,
			"row_template": "accounts/doctype/subscription/templates/subscription_row.html",
			"list_template": "accounts/doctype/subscription/templates/subscription_list.html",
			"subscription_templates": templates,
			"header_action": frappe.render_template(
				"templates/includes/subscriptions/subscription_list_header.html",
				{"subscription_templates": templates},
			)
			if templates
			else None,
			"base_scripts": ["frappe-web.bundle.js", "dialog.bundle.js", "controls.bundle.js"],
		}
	)


def get_subscriptions_list(
	doctype, txt, filters, limit_start, limit_page_length=20, order_by=None, ignore_permissions=False
):
	from frappe.www.list import get_list

	from erpnext.controllers.website_list_for_contact import get_customers_suppliers

	customers, _ = get_customers_suppliers(doctype, frappe.session.user)

	if customers and not ignore_permissions:
		ignore_permissions = True

	if not filters:
		filters = []

	filters.extend([("customer", "in", customers)])

	return get_list(
		doctype,
		txt,
		filters=filters,
		fields=[
			"name",
			"status",
			"start",
			"cancellation_date",
			"current_invoice_start",
			"current_invoice_end",
			"billing_interval",
			"billing_interval_count",
			"grand_total",
		],
		limit_start=limit_start,
		limit_page_length=limit_page_length,
		ignore_permissions=ignore_permissions,
		order_by="modified desc",
	)
