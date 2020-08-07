import frappe
from frappe.utils.data import nowdate, getdate, add_days, get_last_day, add_to_date, flt

class SubscriptionPeriod:
	def __init__(self, subscription, start=None, end=None):
		self.subscription = subscription
		self.start = start or self.subscription.current_invoice_start
		self.end = end or self.subscription.current_invoice_end

	def validate(self):
		current_invoice_start = self.get_current_invoice_start()
		if self.subscription.current_invoice_start != current_invoice_start:
			self.subscription.current_invoice_start = current_invoice_start

		current_invoice_end = self.get_current_invoice_end()
		if self.subscription.current_invoice_end != current_invoice_end:
			self.subscription.current_invoice_end = current_invoice_end
			if not self.subscription.is_new():
				self.subscription.add_subscription_event("New period")

	def get_current_invoice_start(self):
		if SubscriptionStateManager(self.subscription).is_trial():
			return None
		elif self.subscription.is_new():
			return self.subscription.start
		elif self.subscription.get_doc_before_save() \
			and self.subscription.get_doc_before_save().billing_interval != self.subscription.billing_interval:
			return add_days(self.end, 1) if getdate(nowdate()) > self.end else self.start
		elif getdate(self.subscription.current_invoice_end) < getdate(nowdate()):
			return self.get_next_period_start()
		else:
			return self.subscription.current_invoice_start

	def get_current_invoice_end(self):
		if SubscriptionStateManager(self.subscription).is_trial():
			return None
		elif self.subscription.is_new():
			return self.get_next_period_end()
		elif getdate(self.subscription.current_invoice_end) < getdate(self.subscription.current_invoice_start):
			return self.get_next_period_end()
		else:
			return self.subscription.current_invoice_end

	def get_next_period_start(self):
		if not self.subscription.current_invoice_start:
			return max(getdate(self.subscription.start), add_days(getdate(self.subscription.trial_period_end), 1))

		if getdate(self.subscription.current_invoice_end) < getdate(nowdate()):
			return add_days(self.get_next_period_end(), 1)

	def get_next_period_end(self):
		if self.get_billing_cycle_data():
			return add_to_date(self.subscription.current_invoice_start, **self.get_billing_cycle_data())
		else:
			return get_last_day(self.subscription.current_invoice_start)

	def get_billing_cycle_data(self):
		data = {}
		interval = self.subscription.billing_interval
		interval_count = self.subscription.billing_interval_count
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

	def get_current_documents(self, doctype):
		events = [x.document_name for x in frappe.get_all("Subscription Event",
			filters={"subscription": self.subscription.name, "document_type": doctype,
				"period_start": self.start, "period_end": self.end,
				"event_type": f"{doctype.capitalize()} created"},
			fields=["document_name"])]

		transaction_date = "posting_date" if doctype == "Sales Invoice" else "transaction_date"
		documents = frappe.get_all(doctype,
			filters={
				"subscription": self.subscription.name,
				"docstatus": 1
			},
			or_filters={
				transaction_date: ["between", [self.start, self.end]],
				"name": ["in", events]
			})

		return documents

	def get_previous_period(self):
		events = [x.document_name for x in frappe.get_all("Subscription Event",
			filters={"subscription": self.subscription.name,
				"period_end": add_days(self.start, -1),
				"event_type": "New period"},
			fields=["period_start", "period_end"])]

class SubscriptionStateManager:
	def __init__(self, subscription=None):
		self.subscription = subscription

	def set_status(self):
		status = 'Active'
		if self.is_cancelled():
			status = 'Cancelled'
		elif not self.is_cancelled() and self.is_trial():
			status = 'Trial'
		elif not self.is_cancelled() and not self.is_trial():
			if self.is_billable():
				status = 'Billable'
			elif self.is_payable():
				status = 'Payable'
			elif flt(self.subscription.outstanding_amount) > 0:
				status = 'Unpaid'
			else:
				status = 'Paid'

		if status != self.subscription.status:
			self.subscription.db_set("status", status)
			self.subscription.reload()

	def is_trial(self):
		return getdate(self.subscription.trial_period_end) >= getdate(nowdate()) if self.subscription.trial_period_start else False

	def is_cancelled(self):
		return getdate(self.subscription.cancellation_date) <= getdate(nowdate()) if self.subscription.cancellation_date else False

	def is_billable(self):
		if self.subscription.generate_invoice_at_period_start:
			return SubscriptionPeriod(self.subscription).get_current_documents("Sales Invoice")
		else:
			previous_period = SubscriptionPeriod(self.subscription).get_previous_period()
			return not(SubscriptionPeriod(self.subscription,
				start=previous_period[0].period_start,
				end=previous_period[0].period_end
			).get_current_documents("Sales Invoice")) if previous_period else True

	def is_payable(self):
		if self.is_cancelled():
			return False

		if frappe.get_all("Subscription Event",
			filters={
				"event_type": "Payment request created",
				"period_start": self.subscription.current_invoice_start ,
				"period_end": self.subscription.current_invoice_end,
				"subscription": self.subscription.name
			}
		):
			return False

		current_sales_invoices = SubscriptionPeriod(self.subscription).get_current_documents("Sales Invoice")
		current_sales_orders = SubscriptionPeriod(self.subscription).get_current_documents("Sales Order")
		if current_sales_invoices or current_sales_orders:
			for doc in current_sales_invoices:
				if frappe.get_all("Payment Request", filters={"reference_doctype": "Sales Invoice", "reference_name": doc}):
					return False

			for doc in current_sales_orders:
				if frappe.get_all("Payment Request", filters={"reference_doctype": "Sales Order", "reference_name": doc}):
					return False

		return True