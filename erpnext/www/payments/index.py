# Copyright (c) 2019, Dokos and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import erpnext
from frappe.utils import flt, fmt_money
from frappe import _
from frappe.integrations.utils import get_payment_gateway_controller

def get_context(context):
	context.no_cache = 1
	context.show_sidebar = False

@frappe.whitelist(allow_guest=True)
def get_payment_gateways(link):
	payment_request = frappe.get_doc("Payment Request", dict(payment_key=link))
	payment_gateways = []

	for gateway in payment_request.payment_gateways:
		if frappe.db.exists("Payment Gateway Account",\
			dict(payment_gateway=gateway.payment_gateway, currency=payment_request.currency))\
			and not payment_request.check_immediate_payment_for_gateway(gateway.payment_gateway):
			payment_gateways.append(frappe.db.get_value("Payment Gateway",\
				gateway.payment_gateway, ["name", "title", "icon"], as_dict=True))

	return payment_gateways

@frappe.whitelist(allow_guest=True)
def get_payment_details(link):
	payment_request = frappe.get_doc("Payment Request", dict(payment_key=link))
	reference_document = frappe.get_doc(payment_request.reference_doctype,\
		payment_request.reference_name)
	error = None

	if flt(reference_document.get("outstanding_amount")) == 0 or \
		flt(reference_document.get("advance_paid")) >= flt(reference_document.get("rounded_total")\
		or reference_document.get("grand_total")):
		error = _("This invoice has already been fully paid")

	elif erpnext.get_company_currency(reference_document.get("company")) == payment_request.currency and\
		flt(reference_document.get("outstanding_amount")) < payment_request.grand_total:
		error = _("The outstanding amount for this document is lower than the current payment request.")

	return {
		"doctype": reference_document.doctype,
		"docname": reference_document.name,
		"paymentRequest": payment_request.name,
		"formattedAmount": fmt_money(payment_request.grand_total, currency=payment_request.get("currency")),
		"error": error
	}

@frappe.whitelist(allow_guest=True)
def get_payment_url(link, gateway):
	payment_request = frappe.get_doc("Payment Request", dict(payment_key=link))
	payment_request.db_set("payment_gateway", gateway)
	payment_request.run_method("set_gateway_account")

	return payment_request.get_payment_url(gateway)