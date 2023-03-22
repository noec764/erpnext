from collections import defaultdict

import click
import frappe
from frappe.utils import cint, getdate


def execute():
	# Update references in Booking Credit Ledger
	for bcl in frappe.get_all(
		"Booking Credit Ledger", fields=["name", "reference_doctype", "reference_document"]
	):
		frappe.db.set_value(
			"Booking Credit Ledger",
			bcl.name,
			"booking_credit" if bcl.reference_doctype == "Booking Credit" else "booking_credit_usage",
			bcl.reference_document,
		)

	# Create Booking Credit Type
	booking_credit_conversion = frappe.qb.DocType("Booking Credit Conversion")
	conversions = (
		frappe.qb.from_(booking_credit_conversion)
		.select(booking_credit_conversion.booking_credits_item)
		.run(as_dict=True)
	)
	booking_types = defaultdict(dict)

	for conversion in conversions:
		rules = frappe.get_all(
			"Booking Credit Rule",
			filters={
				"rule_type": "Booking Credits Addition",
				"applicable_for": "Item",
				"applicable_for_document_type": conversion.booking_credits_item,
			},
			fields=["expiration_rule", "expiration_delay"],
		)
		if not rules:
			rules = [None]

		for rule in rules:
			for uom in frappe.get_all(
				"Booking Credit",
				filters={"item": conversion.booking_credits_item},
				pluck="uom",
				distinct=True,
			):
				if not frappe.db.exists(
					"Booking Credit Type", dict(item=conversion.booking_credits_item, uom=uom)
				):
					booking_type = create_booking_credit_type(conversion, uom, rule)
					booking_types[booking_type.item][booking_type.uom] = booking_type.label

	# Handle case of items that have been used without conversion creation
	for booking_credit in frappe.get_all(
		"Booking Credit",
		filters={"docstatus": 1},
		fields=["item", "uom"],
		distinct=True,
	):
		if not frappe.db.exists(
			"Booking Credit Type", dict(item=booking_credit.item, uom=booking_credit.uom)
		):
			booking_type = frappe.new_doc("Booking Credit Type")
			if frappe.db.exists("Booking Credit Type", dict(item=booking_credit.item)):
				booking_type.label = f"{booking_credit.item}-{booking_credit.uom}"
			else:
				booking_type.label = booking_credit.item
			booking_type.item = booking_credit.item
			booking_type.uom = booking_credit.uom
			booking_type.insert(ignore_if_duplicate=True)
			booking_types[booking_type.item][booking_type.uom] = booking_type.label

	for dt in ["Booking Credit", "Booking Credit Usage", "Booking Credit Ledger"]:
		for booking_credit in frappe.get_all(dt, fields=["name", "item", "uom"]):
			bt = booking_types.get(booking_credit.item, {}).get(booking_credit.uom, {})
			if not bt:
				# print(
				# 	f"No booking credit type found for item {booking_credit.item} and uom {booking_credit.uom}"
				# )
				continue

			frappe.db.set_value(dt, booking_credit.name, "booking_credit_type", bt)

	for bc in frappe.get_all("Booking Credit", filters={"docstatus": 1}, fields=["name", "quantity"]):
		frappe.db.set_value("Booking Credit", bc.name, "balance", bc.quantity)

	frappe.db.commit()

	processed_bcl = []
	for key in ["user", "customer"]:
		bcl_by_group = defaultdict(lambda: defaultdict(list))
		for bcl in frappe.get_all(
			"Booking Credit Ledger",
			filters={
				"docstatus": 1,
				"name": ["not in", processed_bcl],
				"booking_credit_type": ("is", "set"),
			},
			order_by="date",
			fields=["*"],
		):
			if not bcl.get(key):
				continue

			bcl_by_group[bcl.get(key)][bcl.booking_credit_type].append(bcl)

		for bclu in bcl_by_group:
			for bct in bcl_by_group[bclu]:
				last_booking_credit = None
				for row in bcl_by_group[bclu][bct]:
					if row.booking_credit:
						last_booking_credit = frappe.get_doc("Booking Credit", row.booking_credit)
						processed_bcl.append(row.name)

					elif last_booking_credit and getdate(last_booking_credit.expiration_date) >= getdate(
						row.date
					):
						allocation = min(cint(row.credits) * -1, cint(last_booking_credit.balance))

						last_booking_credit.append(
							"booking_credit_ledger_allocation",
							{"booking_credit_ledger": row.name, "allocation": allocation},
						)

						last_booking_credit.flags.ignore_permissions = True
						last_booking_credit.flags.ignore_links = True
						last_booking_credit.flags.ignore_mandatory = True
						last_booking_credit.save()
						processed_bcl.append(row.name)

	for bc in frappe.get_all("Booking Credit"):
		doc = frappe.get_doc("Booking Credit", bc.name)
		doc.set_status(update=True, update_modified=False)

	for reference in frappe.get_all(
		"Booking Credit Usage Reference",
		filters={"reference_doctype": "Item Booking"},
		fields=["reference_document", "booking_credit_usage"],
	):
		frappe.db.set_value(
			"Booking Credit Usage",
			reference.booking_credit_usage,
			"item_booking",
			reference.reference_document,
		)

	for pr in frappe.get_all("Pricing Rule", filters={"booking_credits_based": 1}):
		frappe.delete_doc("Pricing Rule", pr.name, force=True)

	frappe.db.commit()

	if frappe.get_all("Booking Credit Type"):
		notify_users()


def create_booking_credit_type(conversion, uom, rule):
	booking_credit_conversions = frappe.qb.DocType("Booking Credit Conversions")
	booking_credit_conversion = frappe.qb.DocType("Booking Credit Conversion")

	booking_type = frappe.new_doc("Booking Credit Type")
	if frappe.db.exists("Booking Credit Type", dict(item=conversion.booking_credits_item)):
		booking_type.label = f"{conversion.booking_credits_item}-{uom}"
	else:
		booking_type.label = conversion.booking_credits_item
	booking_type.item = conversion.booking_credits_item
	booking_type.uom = uom
	if rule:
		booking_type.validity = get_validity(rule)

	conversion_table = (
		frappe.qb.from_(booking_credit_conversions)
		.inner_join(booking_credit_conversion)
		.on(booking_credit_conversion.name == booking_credit_conversions.parent)
		.select(booking_credit_conversions.convertible_item)
		.distinct()
		.run(as_dict=True)
	)
	for con in conversion_table:
		booking_type.append("conversion_table", {"item": con.convertible_item, "uom": uom, "credits": 1})

	return booking_type.insert(ignore_if_duplicate=True)


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


def notify_users():

	click.secho(
		"Le fonctionnement des crédits de réservation a été modifié.\n"
		"Un script de migration a basculé les anciennes de règles de crédit de réservation vers les nouveau type de document 'Type de crédit de réservation'.\n"
		"Nous n'avons pas pu ajouter automatiquement les règles d'allocation périodiques (ex. 2 heures de salle de réunion par semaine) dans les abonnements.\n"
		"Vous trouverez une documentation sur ce sujet ici:"
		"https://doc.dokos.io/dokos/lieu/credit-reservation",
		fg="yellow",
	)

	note = frappe.new_doc("Note")
	note.title = "Améliorations des crédits de réservation"
	note.public = 1
	note.notify_on_login = 1
	note.content = """<div class="ql-editor read-mode"><p>Le fonctionnement des crédits de réservation a été modifié.</p><p>Un script de migration a basculé les anciennes de règles de crédit de réservation vers les nouveau type de document <strong>Type de crédit de réservation</strong></p><p>Nous n\'avons pas pu ajouter automatiquement les règles d\'allocation périodiques (ex. 2 heures de salle de réunion par semaine) dans les abonnements.</p><p>Vous trouverez une documentation sur ce sujet à cette adresse: <a href='https://doc.dokos.io/dokos/lieu/credit-reservation'>https://doc.dokos.io/dokos/lieu/credit-reservation</a></p></div>"""
	note.insert(ignore_mandatory=True)
