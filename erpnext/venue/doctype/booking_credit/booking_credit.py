# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime, nowdate

from erpnext.controllers.status_updater import StatusUpdater
from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry
from erpnext.venue.utils import get_customer


class BookingCredit(StatusUpdater):
	def validate(self):
		if not self.customer:
			self.customer = get_customer(self.user)

		self.set_expiration_date()
		self.set_balance()
		self.set_status()

	def before_update_after_submit(self):
		self.set_balance()

	def set_expiration_date(self):
		if not self.expiration_date:
			validity = frappe.db.get_value("Booking Credit Type", self.booking_credit_type, "validity")
			if validity:
				self.expiration_date = add_to_date(self.date, seconds=cint(validity))

	def before_submit(self):
		self.balance = self.quantity

	def on_submit(self):
		ledger_entry = {
			"user": self.user,
			"customer": self.customer,
			"date": self.date,
			"credits": self.quantity,
			"booking_credit": self.name,
			"expiration_date": self.expiration_date,
			"booking_credit_type": self.booking_credit_type,
		}

		create_ledger_entry(**ledger_entry)
		self.check_if_expired(frappe._dict(**ledger_entry, name=self.name))
		self.set_status(update=True)

	def check_if_expired(self, ledger_entry):
		if (
			self.expiration_date
			and get_datetime(self.expiration_date) < now_datetime()
			and not self.is_expired
		):
			_process_expired_booking_entry(ledger_entry)
			self.reload()

	def on_cancel(self):
		doc = frappe.get_doc(
			"Booking Credit Ledger",
			dict(booking_credit=self.name, booking_credit_usage=["is", "not set"], docstatus=1),
		)
		doc.flags.ignore_permissions = True
		doc.cancel()
		self.set_status(update=True)

		for bcl in frappe.get_all(
			"Booking Credit Ledger",
			filters=dict(booking_credit=self.name, booking_credit_usage=["is", "set"], docstatus=1),
		):
			bcl_doc = frappe.get_doc("Booking Credit Ledger", bcl)
			bcl_doc.booking_credit = None
			bcl_doc.run_method("calculate_fifo_balance")

	def set_balance(self):
		self.balance = cint(self.quantity) - sum(
			[a.allocation for a in self.booking_credit_ledger_allocation]
		)


def add_booking_credits(doc, method):
	"""Adds booking credits from a validated sales invoice"""
	if not frappe.db.exists("Booking Credit Type", dict(disabled=0)):
		return

	_add_booking_credits(doc)


def _add_booking_credits(doc):
	grouped_items = defaultdict(lambda: defaultdict(float))
	for item in doc.get("items"):
		grouped_items[item.item_code][item.uom] += flt(item.qty)

	for grouped_item in grouped_items:
		for uom in grouped_items[grouped_item]:
			if credit_type := frappe.get_cached_value(
				"Booking Credit Type",
				dict(item=grouped_item, uom=uom, disabled=0),
				["credits", "name"],
				as_dict=True,
			):
				booking_credit = frappe.get_doc(
					{
						"doctype": "Booking Credit",
						"date": doc.posting_date,  # TODO: See how to implement delayed date
						"customer": doc.customer,
						"quantity": flt(grouped_items[grouped_item][uom]) * cint(credit_type.credits),
						"sales_invoice": doc.name,
						"booking_credit_type": credit_type.name,
					}
				)
				booking_credit.flags.ignore_permissions = True
				booking_credit.insert()
				booking_credit.submit()


def automatic_booking_credit_allocation(subscription):
	for rule in subscription.booking_credits_allocation:
		if last_generated_credit := get_last_credit_for_customer(
			subscription.customer, rule.booking_credit_type, subscription=subscription.name
		):
			if not are_subscription_credits_due(last_generated_credit[0].date, rule, subscription):
				continue

		booking_credit = frappe.get_doc(
			{
				"doctype": "Booking Credit",
				"date": nowdate(),
				"customer": subscription.customer,
				"quantity": cint(rule.quantity),
				"subscription": subscription.name,
				"expiration": rule.expiration,
				"booking_credit_type": rule.booking_credit_type,
			}
		)
		booking_credit.flags.ignore_permissions = True
		booking_credit.insert()
		booking_credit.submit()


def are_subscription_credits_due(date, rule, subscription):
	from dateutil import rrule

	if rule.recurrence == "Once":
		return False

	if rule.recurrence == "Every Billing Period":
		if getdate(date) != getdate() and getdate() == getdate(subscription.current_invoice_start):
			return True
		return False

	if rule.recurrence == "Every Day":
		frequency = rrule.DAILY

	elif rule.recurrence == "Every Week":
		frequency = rrule.WEEKLY

	elif rule.recurrence == "Every Month":
		frequency = rrule.MONTHLY

	end_date = getdate(subscription.cancellation_date or subscription.current_invoice_end)
	possible_dates = [
		getdate(x)
		for x in rrule.rrule(
			frequency, dtstart=get_datetime(subscription.start), until=get_datetime(end_date)
		)
	]

	if getdate(date) != getdate() and getdate() in possible_dates:
		return True


def get_last_credit_for_customer(customer, booking_credit_type, subscription):
	filters = {"customer": customer, "booking_credit_type": booking_credit_type, "docstatus": 1}

	return frappe.get_all(
		"Booking Credit", filters=filters, fields=["name", "date"], order_by="date DESC", limit=1
	)


@frappe.whitelist()
def get_balance(customer, booking_credit_type=None, user=None, date=None):
	"""Returns the booking credit balance for a specific customer and/or user.

	:param customer: id of the customer
	:param booking_credit_type: id of a specific booking credit type
	:param user: id of a user --> Must be linked to the customer provided
	:param date: date of the balance
	"""

	if not date:
		date = nowdate()

	filters = {
		"customer": customer,
		"balance": (">", 0.0),
		"status": "Active",
		"docstatus": 1,
		"date": ("<=", date),
	}

	if booking_credit_type:
		filters["booking_credit_type"] = booking_credit_type

	if user:
		filters["user"] = user

	balance = frappe.get_all(
		"Booking Credit",
		filters=filters,
		fields=["balance", "booking_credit_type"],
	)

	result = defaultdict(int)
	for bal in balance:
		result[bal.booking_credit_type] += bal.balance

	return result


def process_expired_booking_credits():
	expired_entries = frappe.get_all(
		"Booking Credit",
		filters={"is_expired": 0, "expiration_date": ("<", getdate()), "docstatus": 1},
	)
	for expired_entry in expired_entries:
		doc = frappe.get_doc("Booking Credit", expired_entry.name)
		doc.db_set("is_expired", 1)
		doc.set_status(update=True, update_modified=False)


def _process_expired_booking_entry(balance_entry):
	entry = {x: balance_entry[x] for x in balance_entry if x != "name"}
	create_ledger_entry(**entry)
	frappe.db.set_value("Booking Credit", balance_entry.name, "is_expired", 1)
	frappe.db.set_value("Booking Credit", balance_entry.name, "status", "Expired")


def get_booking_credit_types_for_item(item, uom):
	bct = frappe.qb.DocType("Booking Credit Type")
	bctc = frappe.qb.DocType("Booking Credit Type Conversions")
	return (
		frappe.qb.from_(bct)
		.inner_join(bctc)
		.on(bct.name == bctc.parent)
		.select(bct.name)
		.where(bct.disabled == 0)
		.where(bctc.uom == uom)
		.where(bctc.item == item)
	).run(pluck=True)


def get_booking_credits_for_customer(customer, booking_credit_type=None, date=None):
	if not date:
		date = nowdate()
	filters = {"customer": customer, "status": "Active", "date": ("<=", date)}

	if booking_credit_type:
		filters["booking_credit_type"] = booking_credit_type

	return sum(frappe.db.get_all("Booking Credit", filters=filters, pluck="balance"))


def get_converted_qty(booking_credit_type, item):
	return frappe.db.get_value(
		"Booking Credit Type Conversions", {"parent": booking_credit_type, "item": item}, "credits"
	)


@frappe.whitelist()
def has_booking_credits(customer, booking_credit_type=None):
	filters = {"customer": customer, "status": "Active"}
	if booking_credit_type:
		filters["booking_credit_type"] = booking_credit_type

	return bool(frappe.db.get_all("Booking Credit", filters=filters, limit=1))


@frappe.whitelist(allow_guest=True)
def get_booking_credits_by_item(item, uom):
	if frappe.session.user == "Guest":
		return 0.0

	customer = get_customer(frappe.session.user)
	if not customer:
		return 0.0

	booking_credit_types = get_booking_credit_types_for_item(item, uom)
	result = 0.0
	for booking_credit_type in booking_credit_types:
		result += get_booking_credits_for_customer(customer, booking_credit_type)

	return result
