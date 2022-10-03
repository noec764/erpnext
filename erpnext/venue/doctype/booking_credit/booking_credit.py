# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import flt, get_datetime, getdate, now_datetime

from erpnext.controllers.status_updater import StatusUpdater
from erpnext.venue.doctype.booking_credit_ledger.booking_credit_ledger import create_ledger_entry
from erpnext.venue.doctype.item_booking.item_booking import get_uom_in_minutes
from erpnext.venue.utils import get_customer


class BookingCredit(StatusUpdater):
	def validate(self):
		if not self.customer:
			self.customer = get_customer(self.user)
		self.set_status()

	def on_submit(self):
		ledger_entry = {
			"user": self.user,
			"customer": self.customer,
			"date": self.date,
			"credits": self.quantity,
			"reference_doctype": self.doctype,
			"reference_document": self.name,
			"expiration_date": self.expiration_date,
			"uom": self.uom,
			"item": self.item,
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


@frappe.whitelist()
def get_balance(customer, date=None, uom=None):
	default_uom = frappe.db.get_single_value("Venue Settings", "minute_uom")
	query_filters = {"customer": customer, "docstatus": 1}
	if uom:
		query_filters.update({"uom": uom})

	booking_credits = frappe.get_all(
		"Booking Credit Ledger",
		filters=query_filters,
		fields=["credits", "date", "uom", "item"],
		order_by="date DESC",
	)

	if date:
		booking_credits += _process_expired_booking_credits(date=date, customer=customer, submit=False)

	items = list(set([x.item for x in booking_credits if x.item is not None]))
	balance = {}
	for item in items:
		balance[item] = []
		uoms = list(set([x.uom for x in booking_credits if x.uom is not None and x.item == item]))
		for uom in uoms:
			row = {"uom": uom}

			fifo_date = now_datetime()
			for credit in [x for x in booking_credits if x.uom == uom and x.item == item]:
				bal = sum(
					[
						x["credits"]
						for x in booking_credits
						if x.uom == uom and x.item == item and getdate(x["date"]) <= getdate(credit["date"])
					]
				)
				if bal <= 0:
					break
				else:
					fifo_date = credit.date

			row["date"] = fifo_date
			row["balance"] = sum(
				[x["credits"] for x in booking_credits if x["uom"] == uom and x["item"] == item]
			)
			row["conversions"] = []
			balance[item].append(row)

	convertible_items = [
		x
		for x in frappe.get_all("Booking Credit Conversion", pluck="booking_credits_item")
		if x in [y for y in balance]
	]
	for bal in balance:
		if bal not in convertible_items:
			for row in balance[bal]:
				if flt(row.get("balance")) < 0 and row.get("uom") == default_uom:
					for i in convertible_items:
						for r in balance[i]:
							conversion = {
								"uom": r.get("uom"),
								"item": i,
								"qty": flt(
									min(
										get_uom_in_minutes(row.get("uom"))
										* abs(flt(row.get("balance")))
										/ get_uom_in_minutes(r.get("uom")),
										r.get("balance"),
									),
									2,
								),
							}
							if conversion.get("qty") > 0:
								row["conversions"].append(conversion)

	return balance


def process_expired_booking_credits():
	return _process_expired_booking_credits()


def _process_expired_booking_credits(date=None, customer=None, submit=True):
	query_filters = {"is_expired": 0, "expiration_date": ("is", "set"), "docstatus": 1}

	if customer:
		query_filters.update({"customer": customer})

	expired_entries = frappe.get_all(
		"Booking Credit",
		filters=query_filters,
		fields=["name", "quantity", "uom", "customer", "expiration_date", "item"],
	)
	balance_entries = []
	for expired_entry in expired_entries:
		if getdate(expired_entry.expiration_date) >= getdate(date):
			continue

		balance = _calculate_expired_booking_entry(expired_entry, date)

		if balance:
			balance_entries.append(balance)

	if submit:
		for balance_entry in balance_entries:
			_process_expired_booking_entry(balance_entry)

	return balance_entries


def _calculate_expired_booking_entry(expired_entry, date):
	balance = sum(
		frappe.get_all(
			"Booking Credit Ledger",
			filters={
				"customer": expired_entry.customer,
				"date": ("<=", get_datetime(date)),
				"docstatus": 1,
				"uom": expired_entry.uom,
			},
			order_by="date DESC",
			pluck="credits",
		)
	)

	credits_left = sum(
		frappe.get_all(
			"Booking Credit",
			filters={
				"customer": expired_entry.customer,
				"is_expired": 0,
				"date": (">=", expired_entry.date),
				"uom": expired_entry.uom,
				"docstatus": 1,
				"name": ("!=", expired_entry.name),
			},
			pluck="quantity",
		)
	)

	if (balance - credits_left) >= 0:
		return frappe._dict(
			{
				"user": expired_entry.user,
				"customer": expired_entry.customer,
				"date": get_datetime(expired_entry.expiration_date),
				"credits": min(expired_entry.quantity, credits_left) * -1,
				"reference_doctype": "Booking Credit",
				"reference_document": expired_entry.name,
				"uom": expired_entry.uom,
				"item": expired_entry.item,
				"name": expired_entry.name,
			}
		)

	return {}


def _process_expired_booking_entry(balance_entry):
	entry = {x: balance_entry[x] for x in balance_entry if x != "name"}
	create_ledger_entry(**entry)
	frappe.db.set_value("Booking Credit", balance_entry.name, "is_expired", 1)
	frappe.db.set_value("Booking Credit", balance_entry.name, "status", "Expired")


@frappe.whitelist()
def has_booking_credits(customer):
	return bool(frappe.db.get_all("Booking Credit", filters={"customer": customer}, limit=1))
