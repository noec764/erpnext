# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe import _
from erpnext.shopping_cart.doctype.shopping_cart_settings.shopping_cart_settings import show_attachments

def get_context(context):
	context.no_cache = 1
	context.show_sidebar = True
	context.doc = frappe.get_doc(frappe.form_dict.doctype, frappe.form_dict.name)

	if hasattr(context.doc, "set_indicator"):
		context.doc.set_indicator()

	if show_attachments():
		context.attachments = get_attachments(frappe.form_dict.doctype, frappe.form_dict.name)

	context.parents = frappe.form_dict.parents
	context.title = frappe.form_dict.name
	context.payment_ref = frappe.db.get_value("Payment Request", {"reference_name": frappe.form_dict.name}, "name")

	context.enabled_checkout = frappe.get_doc("Shopping Cart Settings").enable_checkout

	default_print_format = frappe.db.get_value('Property Setter', dict(property='default_print_format', doc_type=frappe.form_dict.doctype), "value")
	context.print_format = default_print_format if default_print_format else "Standard"

	if not frappe.has_website_permission(context.doc):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	customer_name = context.doc.party_name if context.doc.doctype == "Quotation" else context.doc.customer
	
	# check for the loyalty program of the customer
	customer_loyalty_program = frappe.db.get_value("Customer", customer_name, "loyalty_program")
	if customer_loyalty_program:
		from erpnext.accounts.doctype.loyalty_program.loyalty_program import get_loyalty_program_details_with_points
		loyalty_program_details = get_loyalty_program_details_with_points(customer_name, customer_loyalty_program)
		context.available_loyalty_points = int(loyalty_program_details.get("loyalty_points"))

def get_attachments(dt, dn):
	return frappe.get_all("File",
		fields=["name", "file_name", "file_url", "is_private"],
		filters = {"attached_to_name": dn, "attached_to_doctype": dt, "is_private":0})
