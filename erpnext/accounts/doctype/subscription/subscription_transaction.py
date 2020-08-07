import frappe
import erpnext
from frappe import _
from frappe.utils.data import nowdate, getdate, cint, add_days, date_diff, flt
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions

from erpnext.accounts.doctype.subscription.subscription_state_manager import SubscriptionPeriod
from erpnext.accounts.doctype.subscription.subscription_plans_manager import SubscriptionPlansManager

class SubscriptionTransactionBase:
	def __init__(self, subscription):
		self.subscription = subscription

	def set_subscription_invoicing_details(self, document, prorate=0):
		document.customer = self.subscription.customer
		document.customer_group, document.territory = frappe.db.get_value("Customer", self.subscription.customer, ["customer_group", "territory"])
		document.set_missing_lead_customer_details()
		document.subscription = self.subscription.name
		document.ignore_pricing_rule = 1 if self.get_plans_pricing_rules() and "Fixed rate" in list(self.get_plans_pricing_rules()) else 0

		items_list = self.get_items_from_plans([p for p in self.subscription.plans if p.status == "Active"],\
			document.posting_date if document.doctype == "Sales Invoice" else document.transaction_date, prorate)
		for item in items_list:
			document.append('items', item)

		# Shipping
		if self.subscription.shipping_rule:
			document.shipping_rule = self.subscription.shipping_rule
			document.apply_shipping_rule()

		# Taxes
		if self.subscription.tax_template:
			document.taxes_and_charges = self.subscription.tax_template
		else:
			from erpnext.accounts.party import set_taxes
			document.taxes_and_charges = set_taxes(
				party=self.subscription.customer,
				party_type="Customer",
				posting_date=document.posting_date if document.doctype == "Sales Invoice" else document.transaction_date,
				company=self.subscription.company,
				customer_group=frappe.db.get_value("Customer", self.subscription.customer, "customer_group"),
				tax_category=document.tax_category,
				billing_address=document.customer_address,
				shipping_address=document.shipping_address_name
			)
		document.set_taxes()

		self.add_due_date(document)

		# Discounts
		if self.subscription.additional_discount_percentage:
			document.additional_discount_percentage = self.subscription.additional_discount_percentage

		if self.subscription.additional_discount_amount:
			document.discount_amount = self.subscription.additional_discount_amount

		if self.subscription.additional_discount_percentage or self.subscription.additional_discount_amount:
			discount_on = self.subscription.apply_additional_discount
			document.apply_discount_on = discount_on if discount_on else 'Grand Total'

		self.add_subscription_dates(document)

		# Terms and conditions
		if self.subscription.terms_and_conditions:
			from erpnext.setup.doctype.terms_and_conditions.terms_and_conditions import get_terms_and_conditions
			document.tc_name = self.subscription.terms_and_conditions
			document.terms = get_terms_and_conditions(self.subscription.terms_and_conditions, document.__dict__)

		return document

	def get_plans_pricing_rules(self):
		rules = set()
		for plan in self.subscription.plans:
			if plan.status == "Active":
				rules.add(plan.price_determination)

		return rules

	def add_due_date(self, document):
		document.append(
			'payment_schedule',
			{
				'due_date': self.get_due_date(),
				'invoice_portion': 100
			}
		)

	def get_due_date(self):
		return add_days(self.subscription.current_invoice_start if \
			self.subscription.generate_invoice_at_period_start else self.subscription.current_invoice_end, cint(self.subscription.days_until_due))

	def add_subscription_dates(self, document):
		document.from_date = self.subscription.current_invoice_start
		document.to_date = self.subscription.current_invoice_end

	def get_items_from_plans(self, plans, date, prorate=0):
		if prorate:
			prorata_factor = self.get_prorata_factor()

		items = []
		for plan in plans:
			if not prorate:
				items.append({'item_code': plan.item, 'qty': plan.qty, \
					'rate': SubscriptionPlansManager(self.subscription).get_plan_rate(plan, getdate(date)),\
					'description': plan.description})
			else:
				items.append({'item_code': plan.item, 'qty': plan.qty, \
					'rate': (SubscriptionPlansManager(self.subscription).get_plan_rate(plan, getdate(date)) * prorata_factor),\
					'description': plan.description})

		return items

	def get_prorata_factor(self):
		consumed = flt(date_diff(self.subscription.cancellation_date, self.subscription.current_invoice_start) + 1)
		plan_days = flt(date_diff(self.subscription.current_invoice_end, self.subscription.current_invoice_start) + 1)
		prorata_factor = consumed / plan_days

		return prorata_factor


class SubscriptionInvoiceGenerator(SubscriptionTransactionBase):
	def create_invoice(self, prorate, simulate=False, payment_entry=None):
		current_sales_orders = SubscriptionPeriod(self.subscription).get_current_documents("Sales Order")
		if current_sales_orders and not simulate:
			from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
			invoice = make_sales_invoice(current_sales_orders[0], ignore_permissions=True)
			self.add_due_date(invoice)
			self.add_subscription_dates(invoice)

		else:
			invoice = frappe.new_doc('Sales Invoice')
			invoice.flags.ignore_permissions = True
			invoice = self.set_subscription_invoicing_details(invoice, prorate)

		invoice.set_posting_time = 1
		invoice.posting_date = self.subscription.current_invoice_start if self.subscription.generate_invoice_at_period_start else self.subscription.current_invoice_end
		invoice.posting_date = self.subscription.current_invoice_start if self.subscription.generate_invoice_at_period_start else self.subscription.current_invoice_end
		invoice.tax_id = frappe.db.get_value("Customer", invoice.customer, "tax_id")
		invoice.currency = self.subscription.currency

		## Add dimensions in invoice for subscription:
		accounting_dimensions = get_accounting_dimensions()

		for dimension in accounting_dimensions:
			if self.subscription.get(dimension):
				invoice.update({
					dimension: self.subscription.get(dimension)
				})

		invoice.flags.ignore_mandatory = True
		invoice.set_missing_values()
		if not simulate:
			invoice.save()

			if payment_entry:
				invoice = self.add_advances(invoice, payment_entry)
				invoice.save()

			if self.subscription.submit_invoice:
				invoice.submit()

		return invoice

	def add_advances(self, invoice, payment_entry):
		pe = frappe.db.get_value("Payment Entry", payment_entry, ["remarks", "unallocated_amount"], as_dict=True)

		invoice.append("advances", {
				"doctype": "Sales Invoice Advance",
				"reference_type": "Payment Entry",
				"reference_name": payment_entry,
				"remarks": pe.get("remarks"),
				"advance_amount": flt(pe.get("unallocated_amount")),
				"allocated_amount": min(flt(invoice.outstanding_amount), flt(pe.get("unallocated_amount")))
			})

		return invoice

	def get_simulation(self):
		try:
			invoice = self.create_invoice(simulate=True)
			# Hack to avoid mandatory sales orders and delivery notes
			invoice.is_pos = True
			invoice.update_stock = True
			invoice._action = "save"
			invoice.run_method("validate")

			return invoice.grand_total
		except erpnext.exceptions.PartyDisabled:
			if not self.is_cancelled():
				self.subscription.reload()
				self.subscription.cancel_subscription()
		except Exception:
			frappe.log_error(frappe.get_traceback(), _("Subscription Grand Total Simulation Error"))
			return

class SubscriptionSalesOderGenerator(SubscriptionTransactionBase):
	def create_new_sales_order(self):
		sales_order = frappe.new_doc('Sales Order')
		sales_order.flags.ignore_permissions = True
		sales_order.transaction_date = self.subscription.current_invoice_start
		sales_order.delivery_date = self.subscription.current_invoice_start if self.subscription.generate_invoice_at_period_start else self.subscription.current_invoice_end
		sales_order = self.set_subscription_invoicing_details(sales_order)
		sales_order.currency = self.subscription.currency
		sales_order.order_type = "Maintenance"

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

		bank_account = self.get_bank_account()		# Subscription is better suited for service items. It won't update `update_stock`
		# for that reason

		payment_entry.posting_date = nowdate()
		payment_entry.company = self.subscription.company
		payment_entry.paid_amount = self.subscription.grand_total
		payment_entry.party = self.subscription.customer
		payment_entry.paid_from = get_party_account("Customer", self.subscription.customer, self.subscription.company)
		payment_entry.paid_from_account_currency = get_account_currency(payment_entry.paid_from)
		payment_entry.bank_account = bank_account.name
		payment_entry.paid_to = bank_account.account
		payment_entry.received_amount = self.subscription.grand_total
		payment_entry.reference_no = f"{self.subscription.customer}-{self.subscription.name}"
		payment_entry.reference_date = self.subscription.current_invoice_start if self.subscription.generate_invoice_at_period_start else self.subscription.current_invoice_end

		payment_entry.payment_type = "Receive"
		payment_entry.party_type = "Customer"
		payment_entry.paid_to_account_currency = self.currency

		return payment_entry

	def get_bank_account(self):
		bank_account_name = None
		if self.subscription.payment_gateway:
			gateway_settings = frappe.db.get_value("Payment Gateway", self.subscription.payment_gateway, ["gateway_settings", "gateway_controller"])
			bank_account_name = frappe.db.get_value(gateway_settings[0], gateway_settings[1], "bank_account")

		if not bank_account_name:
			bank_account_name = frappe.db.get_value("Bank Account",
				{"is_default": 1, "is_company_account": 1, "company": erpnext.get_default_company()}, "name")

		if not bank_account_name:
			frappe.thow(_("Please define a default company bank account"))

		return frappe.get_doc("Bank Account", bank_account_name)

class SubscriptionPaymentRequestGenerator:
	def __init__(self, subscription):
		self.subscription = subscription

	def make_payment_request(self):
		if self.subscription.generate_payment_request and self.subscription.status == "Payable" and not frappe.conf.mute_payment_gateways:
			payment_request = self.create_payment_request(submit=True, mute_email=True)

			if self.subscription.payment_gateway in self.get_immediate_payment_gateways() and \
				payment_request.get("payment_gateway_account") and float(payment_request.get("grand_total")) > 0:
				doc = frappe.get_doc("Payment Request", payment_request.get("name"))
				doc.run_method("process_payment_immediately")

	@staticmethod
	def get_immediate_payment_gateways():
		return [x.name for x in frappe.get_all("Payment Gateway", filters={"gateway_settings": "GoCardless Settings"})]

	def create_payment_request(self, submit=False, mute_email=True):
		from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request
		return make_payment_request(**{
			"dt": self.subscription.doctype,
			"dn": self.subscription.name,
			"party_type": "Customer",
			"party": self.subscription.customer,
			"submit_doc": submit,
			"mute_email": mute_email,
			"payment_gateway": self.subscription.payment_gateway,
			"currency": self.subscription.currency
		})