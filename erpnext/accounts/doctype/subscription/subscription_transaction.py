# Copyright (c) 2021, Dokos SAS and Contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.data import add_days, cint, date_diff, flt, getdate, nowdate

import erpnext
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
)
from erpnext.accounts.doctype.subscription.subscription_plans_manager import (
	SubscriptionPlansManager,
)
from erpnext.accounts.doctype.subscription.subscription_state_manager import SubscriptionPeriod
from erpnext.controllers.accounts_controller import add_taxes_from_tax_template
from erpnext.setup.doctype.terms_and_conditions.terms_and_conditions import (
	get_terms_and_conditions,
)


class SubscriptionTransactionBase:
	def __init__(self, subscription, start_date=None, end_date=None):
		self.subscription = subscription
		self.start_date = (
			start_date or self.subscription.current_invoice_start or self.subscription.start
		)
		self.end_date = end_date or self.subscription.current_invoice_end
		previous_period = SubscriptionPeriod(
			self.subscription, start=self.start_date, end=self.end_date
		).get_previous_period()
		self.previous_period = (
			previous_period[0]
			if previous_period
			else frappe._dict(period_start=self.subscription.start, period_end=self.subscription.start)
		)

	def set_subscription_invoicing_details(self, document):
		document.company = self.subscription.company
		document.customer = self.subscription.customer
		document.customer_group, document.territory = frappe.db.get_value(
			"Customer", self.subscription.customer, ["customer_group", "territory"]
		)
		document.letter_head = frappe.db.get_value(
			"Company", self.subscription.company, "default_letter_head"
		)

		# Keep to update the price list correctly
		default_price_list = document.selling_price_list
		document.selling_price_list = None

		document.set_missing_lead_customer_details()

		if not document.selling_price_list:
			document.selling_price_list = default_price_list

		document.subscription = self.subscription.name
		document.ignore_pricing_rule = (
			1
			if self.get_plans_pricing_rules() and "Fixed rate" in list(self.get_plans_pricing_rules())
			else 0
		)

		items_list = self.get_items_from_plans(
			[p for p in self.subscription.plans if p.status == "Active"], document
		)
		if not items_list:
			frappe.throw(_("Please configure at least one active item for your subscription."))

		for item in items_list:
			document.append("items", item)

		# Shipping
		if self.subscription.shipping_rule:
			document.shipping_rule = self.subscription.shipping_rule
			document.apply_shipping_rule()

		self.add_due_date(document)

		# Discounts
		if self.subscription.additional_discount_percentage:
			document.additional_discount_percentage = self.subscription.additional_discount_percentage

		if self.subscription.additional_discount_amount:
			document.discount_amount = self.subscription.additional_discount_amount

		if (
			self.subscription.additional_discount_percentage or self.subscription.additional_discount_amount
		):
			discount_on = self.subscription.apply_additional_discount
			document.apply_discount_on = discount_on if discount_on else "Grand Total"

		self.add_subscription_dates(document)

		# Terms and conditions
		document.tc_name = self.subscription.terms_and_conditions or frappe.db.get_value(
			"Company", self.subscription.company, "default_selling_terms"
		)
		if document.tc_name:
			document.terms = get_terms_and_conditions(document.tc_name, document.__dict__)

		document.set_missing_values()

		for item in document.items:
			add_taxes_from_tax_template(item, document)

		# Taxes
		if self.subscription.tax_template:
			document.taxes = []
			document.taxes_and_charges = self.subscription.tax_template
		elif not document.get("taxes"):
			from erpnext.accounts.party import set_taxes

			frappe.form_dict["doctype"] = document.doctype
			document.taxes_and_charges = set_taxes(
				party=self.subscription.customer,
				party_type="Customer",
				posting_date=document.posting_date
				if document.doctype == "Sales Invoice"
				else document.transaction_date,
				company=self.subscription.company,
				customer_group=frappe.db.get_value("Customer", self.subscription.customer, "customer_group"),
				tax_category=document.tax_category,
				billing_address=document.customer_address,
				shipping_address=document.shipping_address_name,
			)

		document.set_missing_values()

		return document

	def get_plans_pricing_rules(self):
		rules = set()
		for plan in self.subscription.plans:
			if plan.status == "Active":
				rules.add(plan.price_determination)

		return rules

	def add_due_date(self, document):
		document.append(
			"payment_schedule", {"due_date": self.get_due_date(document), "invoice_portion": 100}
		)

	def get_due_date(self, document):
		end_date = (
			self.start_date
			if self.subscription.generate_invoice_at_period_start
			else self.previous_period.period_end
		)
		if document.doctype == "Sales Order":
			end_date = self.end_date

		return add_days(end_date, cint(self.subscription.days_until_due))

	def add_subscription_dates(self, document):
		start_date = (
			self.start_date
			if self.subscription.generate_invoice_at_period_start
			else self.previous_period.period_start
		)
		end_date = (
			self.end_date
			if self.subscription.generate_invoice_at_period_start
			else self.previous_period.period_end
		)

		if document.doctype == "Sales Order":
			start_date = self.start_date
			end_date = self.end_date

		document.from_date = start_date
		document.to_date = end_date

	def get_items_from_plans(self, plans, document):
		prorata_factor = self.get_prorata_factor()
		date = (
			document.posting_date if document.doctype == "Sales Invoice" else document.transaction_date
		)
		items = []
		for plan in plans:
			rate = (
				SubscriptionPlansManager(self.subscription).get_plan_rate(plan, getdate(date)) * prorata_factor
			)
			item = {
				"item_code": plan.item,
				"qty": plan.qty,
				"uom": plan.uom,
				"rate": rate,
				"description": plan.description,
				"discount_percentage": 100
				if (plan.price_determination == "Fixed rate" and not rate)
				else None,
			}

			if document.doctype == "Sales Invoice" and not frappe.db.get_value(
				"Sales Invoice Item", dict(so_detail=self.subscription.sales_order_item)
			):
				item.update(
					{
						"sales_order": frappe.db.get_value(
							"Sales Order Item", self.subscription.sales_order_item, "parent"
						),
						"so_detail": self.subscription.sales_order_item,
					}
				)

			items.append(item)

		return items

	def get_prorata_factor(self):
		prorate = cint(self.subscription.prorate_last_invoice) and (
			self.end_date == self.subscription.cancellation_date
		)
		consumed = flt(date_diff(self.subscription.cancellation_date, self.start_date) + 1)
		plan_days = flt(date_diff(self.end_date, self.start_date) + 1) or 1
		prorata_factor = consumed / plan_days

		return prorata_factor if prorate else 1


class SubscriptionInvoiceGenerator(SubscriptionTransactionBase):
	def create_invoice(self, simulate=False):
		current_sales_orders = SubscriptionPeriod(self.subscription).get_current_documents("Sales Order")
		if current_sales_orders and not simulate:
			from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

			invoice = make_sales_invoice(current_sales_orders[0], ignore_permissions=True)
			self.add_due_date(invoice)
			self.add_subscription_dates(invoice)
			invoice.skip_delivery_note = self.subscription.skip_delivery_note

		else:
			invoice = frappe.new_doc("Sales Invoice")
			invoice.flags.ignore_permissions = True
			invoice = self.set_subscription_invoicing_details(invoice)

		invoice.set_posting_time = 1
		invoice.posting_date = (
			self.start_date
			if self.subscription.generate_invoice_at_period_start
			else self.previous_period.period_end
		)
		invoice.tax_id = frappe.db.get_value("Customer", invoice.customer, "tax_id")
		invoice.currency = self.subscription.currency

		# Add dimensions in invoice for subscription:
		accounting_dimensions = get_accounting_dimensions()

		for dimension in accounting_dimensions:
			if self.subscription.get(dimension):
				invoice.update({dimension: self.subscription.get(dimension)})

		self.add_advances(invoice)
		invoice.flags.ignore_mandatory = True
		invoice.set_missing_values()
		return invoice

	def add_advances(self, invoice):
		if self.subscription.payment_gateway:
			reference = None

			payment_entry = frappe.db.get_value(
				"Payment Entry", dict(reference_no=reference), ["remarks", "unallocated_amount"], as_dict=True
			)
			if payment_entry:
				invoice.append(
					"advances",
					{
						"doctype": "Sales Invoice Advance",
						"reference_type": "Payment Entry",
						"reference_name": payment_entry,
						"remarks": payment_entry.get("remarks"),
						"advance_amount": flt(payment_entry.get("unallocated_amount")),
						"allocated_amount": min(
							flt(invoice.outstanding_amount), flt(payment_entry.get("unallocated_amount"))
						),
					},
				)

				return invoice

	def get_simulation(self):
		try:
			invoice = self.create_invoice(simulate=True)
			# Hack to avoid mandatory sales orders and delivery notes
			invoice.so_dn_required = lambda: None
			invoice.update_stock = True
			invoice._action = "save"
			invoice.run_method("validate")

			return invoice.grand_total
		except erpnext.exceptions.PartyDisabled:
			if not self.is_cancelled():
				self.subscription.reload()
				self.subscription.cancel_subscription()
		except Exception:
			invoice.log_error(_("Subscription Grand Total Simulation Error"))


class SubscriptionSalesOrderGenerator(SubscriptionTransactionBase):
	def create_new_sales_order(self):
		sales_order = frappe.new_doc("Sales Order")
		sales_order.flags.ignore_permissions = True
		sales_order.transaction_date = self.start_date
		sales_order.delivery_date = (
			self.start_date if self.subscription.generate_invoice_at_period_start else self.end_date
		)
		sales_order = self.set_subscription_invoicing_details(sales_order)
		sales_order.currency = self.subscription.currency
		sales_order.order_type = "Sales"
		sales_order.skip_delivery_note = self.subscription.skip_delivery_note

		sales_order.flags.ignore_mandatory = True
		sales_order.set_missing_values()
		sales_order.save()
		sales_order.submit()

		return sales_order


class SubscriptionPaymentEntryGenerator(SubscriptionTransactionBase):
	def create_payment(self):
		from erpnext.accounts.party import get_party_account
		from erpnext.accounts.utils import get_account_currency

		payment_entry = frappe.new_doc("Payment Entry")

		bank_account = self.get_bank_account()

		payment_entry.posting_date = nowdate()
		payment_entry.mode_of_payment = frappe.db.get_value(
			"Payment Gateway", self.subscription.payment_gateway, "mode_of_payment"
		)
		payment_entry.company = self.subscription.company
		payment_entry.paid_amount = self.subscription.grand_total
		payment_entry.party = self.subscription.customer
		payment_entry.paid_from = get_party_account(
			"Customer", self.subscription.customer, self.subscription.company
		)
		payment_entry.paid_from_account_currency = get_account_currency(payment_entry.paid_from)
		payment_entry.bank_account = bank_account.name
		payment_entry.paid_to = bank_account.account
		payment_entry.received_amount = self.subscription.grand_total
		payment_entry.reference_no = f"{self.subscription.customer}-{self.subscription.name}"
		payment_entry.reference_date = (
			self.start_date
			if self.subscription.generate_invoice_at_period_start
			else self.previous_period.period_end
		)

		payment_entry.payment_type = "Receive"
		payment_entry.party_type = "Customer"
		payment_entry.paid_to_account_currency = self.subscription.currency

		return payment_entry

	def get_bank_account(self):
		bank_account_name = None
		if self.subscription.payment_gateway:
			gateway_settings = frappe.db.get_value(
				"Payment Gateway",
				self.subscription.payment_gateway,
				["gateway_settings", "gateway_controller"],
			)
			bank_account_name = frappe.db.get_value(
				gateway_settings[0], gateway_settings[1], "bank_account"
			)

		if not bank_account_name:
			bank_account_name = frappe.db.get_value(
				"Bank Account",
				{"is_default": 1, "is_company_account": 1, "company": erpnext.get_default_company()},
				"name",
			)

		if not bank_account_name:
			frappe.thow(_("Please define a default company bank account"))

		return frappe.get_doc("Bank Account", bank_account_name)


class SubscriptionPaymentRequestGenerator:
	def __init__(self, subscription, invoice=None):
		self.subscription = subscription
		self.invoice = invoice

	def make_payment_request(self):
		if self.subscription.generate_payment_request and self.subscription.status == "Payable":
			frappe.flags.mute_gateways_validation = True
			if flt(self.subscription.grand_total) > 0:
				payment_request = self.create_payment_request(submit=True)
				payment_request_document = frappe.get_doc("Payment Request", payment_request.get("name"))
				frappe.flags.mute_gateways_validation = False

				if (
					not frappe.conf.mute_payment_gateways
					and float(payment_request.get("grand_total")) > 0
					and payment_request_document.check_if_immediate_payment_is_autorized()
				):
					payment_request_document.run_method("process_payment_immediately")

	def get_payment_gateways(self):
		gateways = []
		if self.subscription.payment_gateways_template:
			gateways = [
				{"payment_gateway": x.payment_gateway}
				for x in frappe.get_doc(
					"Portal Payment Gateways Template", self.subscription.payment_gateways_template
				).payment_gateways
			]

		elif self.subscription.subscription_template:
			template = frappe.get_doc("Subscription Template", self.subscription.subscription_template)
			gateways = [{"payment_gateway": x.payment_gateway} for x in template.payment_gateways]

		if not gateways:
			gateways = [
				{"payment_gateway": x.name} for x in frappe.get_all("Payment Gateway", filters={"disabled": 0})
			]

		return gateways

	def create_payment_request(self, submit=False):
		from erpnext.accounts.doctype.payment_request.payment_request import (
			get_payment_gateway_account,
			make_payment_request,
		)

		link_dt = "Sales Invoice"
		link_dn = self.invoice
		if not link_dn:
			current_orders = SubscriptionPeriod(self.subscription).get_current_documents("Sales Order")
			if current_orders:
				link_dt = "Sales Order"
				link_dn = current_orders[0].get("name")
			else:
				current_invoices = SubscriptionPeriod(self.subscription).get_current_documents("Sales Invoice")
				if current_invoices:
					link_dn = current_invoices[0].get("name")

		pr = frappe.get_doc(
			make_payment_request(
				**{
					"dt": link_dt,
					"dn": link_dn,
					"subscription": self.subscription.name,
					"party_type": "Customer",
					"party": self.subscription.customer,
					"submit_doc": False,
					"mute_email": self.subscription.email_template,
					"currency": self.subscription.currency,
					"email_template": self.subscription.email_template,
					"print_format": self.subscription.print_format,
					"payment_gateways_template": self.subscription.payment_gateways_template,
				}
			)
		)

		if not self.subscription.payment_gateway:
			for gateway in self.get_payment_gateways():
				pr.append("payment_gateways", gateway)

		pr.payment_gateway = (
			self.subscription.payment_gateway if self.subscription.payment_gateway else None
		)
		pr.payment_gateway_account = (
			get_payment_gateway_account(
				{"currency": self.subscription.currency, "payment_gateway": self.subscription.payment_gateway}
			).name
			if self.subscription.payment_gateway
			else None
		)

		if submit:
			pr.insert(ignore_permissions=True)
			pr.submit()

		return pr.as_dict()
