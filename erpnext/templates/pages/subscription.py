# Copyright (c) 2020, Dokos SAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

from frappe import _
from frappe.utils import nowdate, cint, get_url
from erpnext.controllers.website_list_for_contact import get_customers_suppliers
from erpnext.accounts.doctype.subscription_template.subscription_template import make_subscription
from erpnext.shopping_cart.cart import get_party
from erpnext.accounts.doctype.payment_request.payment_request import get_payment_link

def get_context(context):
	context.no_cache = 1
	context.show_sidebar = True
	context.breadcrumbs = True

	context.doc = frappe.get_doc(frappe.form_dict.doctype, frappe.form_dict.name)
	context.next_invoice_date = nowdate()
	context.subscription_plans = get_subscription_plans(context.doc.customer)
	context.payment_requests = get_open_payment_requests_for_subscription(frappe.form_dict.name)

	if not cint(frappe.db.get_single_value("Shopping Cart Settings", "enabled")) \
		or frappe.session.user == "Guest":
		frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

def get_subscription_plans(customer):
	from frappe.utils.nestedset import get_root_of

	customer_group = frappe.db.get_value("Customer", customer, "customer_group")
	root_customer_group = get_root_of("Customer Group")
	plans = frappe.get_all("Subscription Plan", filters={"enable_on_portal": 1, "customer_group": ("in", [customer_group, root_customer_group, None])})

	return [frappe.get_doc("Subscription Plan", plan.name) for plan in plans]

def get_open_payment_requests_for_subscription(subscription):
	output = []
	orders = frappe.get_all("Sales Order", filters={"subscription": subscription}, pluck="name")
	invoices = frappe.get_all("Sales Invoice", filters={"subscription": subscription}, pluck="name")
	payment_requests = frappe.get_all("Payment Request", filters={
		"docstatus": 1,
		"status": "Initiated",
		"reference_doctype": ("in", ("Sales Order", "Sales Invoice")),
		"reference_name": ("in", orders + invoices)
	}, fields=["name", "payment_key", "grand_total", "reference_doctype", "reference_name", "currency"],
	order_by="transaction_date desc")

	references = []
	for payment_request in payment_requests:
		print("payment_request", payment_request)
		if payment_request.reference_doctype == "Sales Invoice":
			invoice = frappe.db.get_value(payment_request.reference_doctype, payment_request.reference_name, ("outstanding_amount", "docstatus"), as_dict=True)
			print(invoice)
			if invoice.docstatus != 1 or not invoice.outstanding_amount:
				frappe.db.set_value("Payment Request", payment_request.name, "status", "Cancelled")
				continue

		elif payment_request.reference_doctype == "Sales Order":
			order = frappe.db.get_value(payment_request.reference_doctype, payment_request.reference_name, ("advance_paid", "docstatus", "status"), as_dict=True)
			if not order.docstatus == 1 or order.outstanding_amount or not order.status in ("Completed", "Closed"):
				frappe.db.set_value("Payment Request", payment_request.name, "status", "Cancelled")
				continue

		if (payment_request.reference_doctype, payment_request.reference_name) not in references:
			payment_request["payment_link"] = get_payment_link(payment_request.payment_key)
			output.append(payment_request)
			references.append((payment_request.reference_doctype, payment_request.reference_name))

	return output

@frappe.whitelist()
def add_plan(subscription, plan):
	subscription = frappe.get_doc("Subscription", subscription)
	subscription.add_plan(plan)
	return subscription.save(ignore_permissions=True)

@frappe.whitelist()
def remove_subscription_line(subscription, line):
	subscription = frappe.get_doc("Subscription", subscription)
	subscription.remove_plan(line)
	return subscription.save(ignore_permissions=True)

@frappe.whitelist()
def new_subscription(template):
	customer = None
	customers, suppliers = get_customers_suppliers("Integration References", frappe.session.user)
	customer = customers[0] if customers else get_party().name

	company = frappe.db.get_single_value("Shopping Cart Settings", "company")

	subscription = make_subscription(template=template, company=company, customer=customer, start_date=nowdate(), ignore_permissions=True)
	payment_key = frappe.db.get_value("Payment Request", {"reference_doctype": "Subscription", "reference_name": subscription.name, "status": "Initiated"}, "payment_key")

	return {
		"subscription": subscription,
		"payment_link": get_url("/payments?link={0}".format(payment_key)) if payment_key else None
	}

@frappe.whitelist()
def cancel_subscription(subscription):
	subscription = frappe.get_doc("Subscription", subscription)
	subscription.cancellation_date = subscription.current_invoice_end
	return subscription.save(ignore_permissions=True)
