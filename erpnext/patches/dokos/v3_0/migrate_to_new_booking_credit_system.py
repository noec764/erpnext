from collections import defaultdict

import frappe
from frappe.utils import cint

def execute():
	conversions = frappe.get_all("Booking Credit Conversion")
	booking_types = defaultdict(dict)

	for conversion in conversions:
		conversion_doc = frappe.get_doc("Booking Credit Conversion", conversion.name)
		for rule in frappe.get_all("Booking Credit Rule", filters={"rule_type": "Booking Credits Addition", "applicable_for": "Item", "applicable_for_document_type": conversion_doc.booking_credits_item}):
			rule = frappe.get_doc("Booking Credit Rule", rule.name)

			for credits in frappe.get_all("Booking Credit", filters={"item": conversion_doc.booking_credits_item}, fields=["uom"], distinct=True):
				booking_type = frappe.new_doc("Booking Credit Type")
				if frappe.db.exists("Booking Credit Type", dict(item=conversion_doc.booking_credits_item)):
					booking_type.label = f"{conversion_doc.booking_credits_item}-{credits.uom}"
				else:
					booking_type.label = conversion_doc.booking_credits_item
				booking_type.item = conversion_doc.booking_credits_item
				booking_type.uom = credits.uom
				booking_type.validity = get_validity(rule)
				for con in conversion_doc.conversion_table:
					booking_type.append("conversion_table", {
						"item": con.convertible_item,
						"credits": 1
					})

				booking_type.insert()

				booking_types[booking_type.item][booking_type.uom] = booking_type.label

	for dt in ["Booking Credit", "Booking Credit Usage", "Booking Credit Ledger"]:
		for booking_credit in frappe.get_all(dt, fields=["name", "item", "uom"]):
			bt = booking_types.get(booking_credit.item, {}).get(booking_credit.uom, {})
			if not bt:
				print(f"No booking credit type found for item {booking_credit.item} and uom {booking_credit.uom}")
				continue

			frappe.db.set_value(dt, booking_credit.name, "booking_credit_type", bt)

	for reference in frappe.get_all("Booking Credit Usage Reference", filters={"reference_doctype": "Item Booking"}, fields=["reference_document", "booking_credit_usage"]):
		frappe.db.set_value("Booking Credit Usage", reference.booking_credit_usage, "item_booking", reference.reference_document)


def get_validity(rule):
	if rule.expiration_rule == "End of the month":
		return 30 * 24 * 3600

	if rule.expiration_rule == "End of the year":
		return 365 * 24 * 3600

	if not rule.expiration_delay:
		return 0

	if rule.expiration_rule == "Add X years":
		return 365 * 24 * 3600 * cint(rule.expiration_delay)

	if rule.expiration_rule == "Add X months":
		return 30 * 24 * 3600 * cint(rule.expiration_delay)

	if rule.expiration_rule == "Add X days":
		return 24 * 3600 * cint(rule.expiration_delay)
