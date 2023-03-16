# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe.utils import flt, get_datetime, now_datetime, cint, add_to_date, nowdate, getdate

from erpnext.controllers.status_updater import StatusUpdater
from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry
from erpnext.venue.utils import get_customer


class BookingCredit(StatusUpdater):
	def validate(self):
		if not self.customer:
			self.customer = get_customer(self.user)

		self.set_expiration_date()
		self.set_status()

	def set_expiration_date(self):
		validity = frappe.db.get_value("Booking Credit Type", self.booking_credit_type, "validity")
		self.expiration_date = add_to_date(self.date, seconds=cint(validity))

	def before_submit(self):
		self.balance = self.quantity

	def on_submit(self):
		ledger_entry = {
			"user": self.user,
			"customer": self.customer,
			"date": self.date,
			"credits": self.quantity,
			"reference_doctype": self.doctype,
			"reference_document": self.name,
			"expiration_date": self.expiration_date,
			"booking_credit_type": self.booking_credit_type
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
			"Booking Credit Ledger", dict(reference_doctype=self.doctype, reference_document=self.name)
		)
		doc.flags.ignore_permissions = True
		doc.cancel()
		self.set_status(update=True)


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
			if credit_type := frappe.get_cached_value("Booking Credit Type", dict(item=grouped_item.item_code, uom=uom, disabled=0), "credits"):
				booking_credit = frappe.get_doc(
					{
						"doctype": "Booking Credit",
						"date": doc.posting_date, #TODO: See how to implement delayed date
						"customer": doc.customer,
						"quantity": flt(grouped_items[grouped_item][uom]) * cint(credit_type.credits),
						"sales_invoice": doc.name
					}
				)
				booking_credit.flags.ignore_permissions = True
				booking_credit.insert()
				booking_credit.submit()

def automatic_booking_credit_allocation(subscription):
	for rule in subscription.booking_credits_allocation:
		if last_generated_credit := get_last_credit_for_customer(subscription.customer, rule.booking_credit_type, subscription=subscription.name):
			if not are_subscription_credits_due(last_generated_credit[0].date, rule, subscription):
				continue

		booking_credit = frappe.get_doc(
			{
				"doctype": "Booking Credit",
				"date": nowdate(),
				"customer": subscription.customer,
				"quantity": cint(rule.quantity),
				"subscription": subscription.name
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
	filters={
			"customer": customer,
			"booking_credit_type": booking_credit_type,
			"docstatus": 1
		}

	return frappe.get_all(
		"Booking Credit",
		filters=filters,
		fields=["name", "date"],
		order_by="date DESC",
		limit=1
	)


@frappe.whitelist()
def get_balance(customer, booking_credit_type=None, user=None):
	"""Returns the booking credit balance for a specific customer and/or user.

	:param customer: id of the customer
	:param date: date of the balance
	:param booking_credit_type: id of a specific booking credit type
	:param user: id of a user --> Must be linked to the customer provided
	"""

	filters={
		"customer": customer,
		"balance": (">", 0.0),
		"status": "Active",
		"docstatus": 1
	}

	if booking_credit_type:
		filters["booking_credit_type"] = booking_credit_type

	if user:
		filters["user"] = user

	balance = frappe.get_all(
		"Booking Credit",
		filters=filters,
		pluck="balance",
	)

	if balance:
		return sum(balance)

	return 0.0


def _process_expired_booking_entry(balance_entry):
	entry = {x: balance_entry[x] for x in balance_entry if x != "name"}
	create_ledger_entry(**entry)
	frappe.db.set_value("Booking Credit", balance_entry.name, "is_expired", 1)
	frappe.db.set_value("Booking Credit", balance_entry.name, "status", "Expired")


@frappe.whitelist()
def has_booking_credits(customer, booking_credit_type=None):
	filters={"customer": customer, "status": "Active"}
	if booking_credit_type:
		filters["booking_credit_type"] = booking_credit_type

	return bool(frappe.db.get_all("Booking Credit", filters=filters, limit=1))



# @frappe.whitelist()
# def get_balance(customer, date=None, uom=None):
# 	default_uom = frappe.db.get_single_value("Venue Settings", "minute_uom")
# 	query_filters = {"customer": customer, "docstatus": 1}
# 	if uom:
# 		query_filters.update({"uom": uom})

# 	booking_credits = frappe.get_all(
# 		"Booking Credit Ledger",
# 		filters=query_filters,
# 		fields=["credits", "date", "uom", "item"],
# 		order_by="date DESC",
# 	)

# 	if date:
# 		booking_credits += _process_expired_booking_credits(date=date, customer=customer, submit=False)

# 	items = list(set([x.item for x in booking_credits if x.item is not None]))
# 	balance = {}
# 	for item in items:
# 		balance[item] = []
# 		uoms = list(set([x.uom for x in booking_credits if x.uom is not None and x.item == item]))
# 		for uom in uoms:
# 			row = {"uom": uom}

# 			fifo_date = now_datetime()
# 			for credit in [x for x in booking_credits if x.uom == uom and x.item == item]:
# 				bal = sum(
# 					[
# 						x["credits"]
# 						for x in booking_credits
# 						if x.uom == uom and x.item == item and getdate(x["date"]) <= getdate(credit["date"])
# 					]
# 				)
# 				if bal <= 0:
# 					break
# 				else:
# 					fifo_date = credit.date

# 			row["date"] = fifo_date
# 			row["balance"] = sum(
# 				[x["credits"] for x in booking_credits if x["uom"] == uom and x["item"] == item]
# 			)
# 			row["conversions"] = []
# 			balance[item].append(row)

# 	convertible_items = [
# 		x
# 		for x in frappe.get_all("Booking Credit Conversion", pluck="booking_credits_item")
# 		if x in [y for y in balance]
# 	]
# 	for bal in balance:
# 		if bal not in convertible_items:
# 			for row in balance[bal]:
# 				if flt(row.get("balance")) < 0 and row.get("uom") == default_uom:
# 					for i in convertible_items:
# 						for r in balance[i]:
# 							conversion = {
# 								"uom": r.get("uom"),
# 								"item": i,
# 								"qty": flt(
# 									min(
# 										get_uom_in_minutes(row.get("uom"))
# 										* abs(flt(row.get("balance")))
# 										/ get_uom_in_minutes(r.get("uom")),
# 										r.get("balance"),
# 									),
# 									2,
# 								),
# 							}
# 							if conversion.get("qty") > 0:
# 								row["conversions"].append(conversion)

# 	return balance


# def process_expired_booking_credits():
# 	return _process_expired_booking_credits()


# def _process_expired_booking_credits(date=None, customer=None, submit=True):
# 	query_filters = {"is_expired": 0, "expiration_date": ("is", "set"), "docstatus": 1}

# 	if customer:
# 		query_filters.update({"customer": customer})

# 	expired_entries = frappe.get_all(
# 		"Booking Credit",
# 		filters=query_filters,
# 		fields=["name", "quantity", "uom", "customer", "expiration_date", "item"],
# 	)
# 	balance_entries = []
# 	for expired_entry in expired_entries:
# 		if getdate(expired_entry.expiration_date) >= getdate(date):
# 			continue

# 		balance = _calculate_expired_booking_entry(expired_entry, date)

# 		if balance:
# 			balance_entries.append(balance)

# 	if submit:
# 		for balance_entry in balance_entries:
# 			_process_expired_booking_entry(balance_entry)

# 	return balance_entries


# def _calculate_expired_booking_entry(expired_entry, date):
# 	balance = sum(
# 		frappe.get_all(
# 			"Booking Credit Ledger",
# 			filters={
# 				"customer": expired_entry.customer,
# 				"date": ("<=", get_datetime(date)),
# 				"docstatus": 1,
# 				"uom": expired_entry.uom,
# 			},
# 			order_by="date DESC",
# 			pluck="credits",
# 		)
# 	)

# 	credits_left = sum(
# 		frappe.get_all(
# 			"Booking Credit",
# 			filters={
# 				"customer": expired_entry.customer,
# 				"is_expired": 0,
# 				"date": (">=", expired_entry.date),
# 				"uom": expired_entry.uom,
# 				"docstatus": 1,
# 				"name": ("!=", expired_entry.name),
# 			},
# 			pluck="quantity",
# 		)
# 	)

# 	if (balance - credits_left) >= 0:
# 		return frappe._dict(
# 			{
# 				"user": expired_entry.user,
# 				"customer": expired_entry.customer,
# 				"date": get_datetime(expired_entry.expiration_date),
# 				"credits": min(expired_entry.quantity, credits_left) * -1,
# 				"reference_doctype": "Booking Credit",
# 				"reference_document": expired_entry.name,
# 				"uom": expired_entry.uom,
# 				"item": expired_entry.item,
# 				"name": expired_entry.name,
# 			}
# 		)

# 	return {}