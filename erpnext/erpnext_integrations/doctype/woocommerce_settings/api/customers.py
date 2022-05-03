import frappe
import frappe.utils.nestedset
from frappe import _
from frappe.contacts.doctype.address.address import get_preferred_address
from frappe.exceptions import DuplicateEntryError, TimestampMismatchError
from frappe.utils import cint

from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI


class WooCommerceCustomers(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceCustomers, self).__init__(version, args, kwargs)

	def get_customers(self, params=None):
		return self.get("customers", params=params)


def get_customers():
	wc_api = WooCommerceCustomers()

	woocommerce_customers = get_woocommerce_customers(wc_api)

	for woocommerce_customer in woocommerce_customers:
		sync_customer(wc_api.settings, woocommerce_customer)


def get_woocommerce_customers(wc_api):
	response = wc_api.get_customers()
	woocommerce_customers = response.json()

	for page_idx in range(1, int(response.headers.get("X-WP-TotalPages")) + 1):
		response = wc_api.get_customers(params={"per_page": 100, "page": page_idx})
		woocommerce_customers.extend(response.json())

	return woocommerce_customers


def sync_customer(settings, woocommerce_customer):
	customer_name = woocommerce_customer.get("billing", {}).get("company")
	customer_type = (
		"Company" if woocommerce_customer.get("billing", {}).get("company") else "Individual"
	)

	if not customer_name:
		customer_name = (
			f'{woocommerce_customer.get("billing", {}).get("first_name")} {woocommerce_customer.get("billing", {}).get("last_name")}'
			if woocommerce_customer.get("billing", {}).get("last_name")
			else None
		)

	if not customer_name:
		customer_name = (
			(
				woocommerce_customer.get("first_name")
				+ " "
				+ (woocommerce_customer.get("last_name") if woocommerce_customer.get("last_name") else "")
			)
			if woocommerce_customer.get("first_name")
			else woocommerce_customer.get("email")
		)

	try:
		if cint(woocommerce_customer.get("id")) and frappe.db.exists(
			"Customer", dict(woocommerce_id=woocommerce_customer.get("id"))
		):
			customer = frappe.get_doc("Customer", dict(woocommerce_id=woocommerce_customer.get("id")))

		elif frappe.db.exists("Customer", dict(woocommerce_email=woocommerce_customer.get("email"))):
			customer = frappe.get_doc("Customer", dict(woocommerce_email=woocommerce_customer.get("email")))

		else:
			# try to match territory
			country_name = get_country_name(woocommerce_customer["billing"]["country"])
			if frappe.db.exists("Territory", country_name):
				territory = country_name
			else:
				territory = frappe.utils.nestedset.get_root_of("Territory")

			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": customer_name,
					"woocommerce_id": woocommerce_customer.get("id"),
					"woocommerce_email": woocommerce_customer.get("email"),
					"customer_group": settings.customer_group,
					"territory": territory,
					"customer_type": customer_type,
				}
			)
			customer.flags.ignore_mandatory = True
			customer.insert(ignore_permissions=True)

		if customer:
			customer.update(
				{
					"customer_name": customer_name,
					"woocommerce_email": woocommerce_customer.get("email"),
					"customer_type": customer_type,
				}
			)
			try:
				customer.flags.ignore_mandatory = True
				customer.flags.ignore_permissions = True
				customer.save()
			except frappe.exceptions.TimestampMismatchError:
				# Handle the update of two sales orders customers details concurrently
				pass

			billing_address = woocommerce_customer.get("billing")
			if billing_address:
				add_billing_address(settings, customer, woocommerce_customer)

			shipping_address = woocommerce_customer.get("shipping")
			if shipping_address:
				add_shipping_address(settings, customer, woocommerce_customer)

			add_contact(customer, woocommerce_customer)

		frappe.db.commit()

		return customer
	except Exception:
		customer.log_error(_("Woocommerce Customer Creation Error"))


def sync_guest_customers(order):
	wc_api = WooCommerceCustomers()
	customer_object = {
		"first_name": order.get("billing", {}).get("first_name"),
		"last_name": order.get("billing", {}).get("last_name"),
		"email": order.get("billing", {}).get("email"),
		"id": 0,
		"billing": order.get("billing"),
		"shipping": order.get("shipping"),
	}

	return sync_customer(wc_api.settings, customer_object)


def add_billing_address(settings, customer, woocommerce_customer):
	existing_address = get_preferred_address("Customer", customer.name, "is_primary_address")
	_add_update_address(settings, customer, woocommerce_customer, "Billing", existing_address)


def add_shipping_address(settings, customer, woocommerce_customer):
	existing_address = get_preferred_address("Customer", customer.name, "is_shipping_address")
	_add_update_address(settings, customer, woocommerce_customer, "Shipping", existing_address)


def _add_update_address(
	settings, customer, woocommerce_customer, address_type, existing_address=None
):
	woocommerce_address = woocommerce_customer.get(address_type.lower())

	country = get_country_name(woocommerce_address.get("country"))
	if not frappe.db.exists("Country", country):
		country = frappe.db.get_value("Company", settings.company, "country")

	try:
		if existing_address:
			doc = frappe.get_doc("Address", existing_address)
		else:
			doc = frappe.new_doc("Address")

		doc.flags.ignore_permissions = True
		doc.update(
			{
				"address_title": customer.name,
				"address_type": address_type,
				"address_line1": woocommerce_address.get("address_1") or "No Address Line 1",
				"address_line2": woocommerce_address.get("address_2"),
				"city": woocommerce_address.get("city") or "City",
				"state": woocommerce_address.get("state"),
				"pincode": woocommerce_address.get("postcode"),
				"country": country,
				"phone": woocommerce_address.get("phone"),
				"email_id": woocommerce_address.get("email"),
				"is_primary_address": address_type == "Billing",
				"is_shipping_address": address_type == "Shipping",
				"links": [{"link_doctype": "Customer", "link_name": customer.name}],
			}
		)
		try:
			doc.save()
		except frappe.exceptions.TimestampMismatchError:
			# Handle the update of two sales orders contact details concurrently
			pass

	except Exception:
		doc.log_error(_("Woocommerce Address Error"))


def add_contact(customer, woocommerce_customer):
	existing_contact = frappe.db.get_value(
		"Contact", dict(email_id=woocommerce_customer["billing"]["email"]), "name"
	)
	try:
		if existing_contact:
			doc = frappe.get_doc("Contact", existing_contact)
		else:
			doc = frappe.new_doc("Contact")

		doc.flags.ignore_permissions = True
		doc.update(
			{
				"first_name": woocommerce_customer["billing"]["first_name"],
				"last_name": woocommerce_customer["billing"]["last_name"],
				"email_ids": [{"email_id": woocommerce_customer["billing"]["email"], "is_primary": 1}],
				"phone_nos": [{"phone": woocommerce_customer["billing"]["phone"], "is_primary_phone": 1}],
				"links": [{"link_doctype": "Customer", "link_name": customer.name}],
			}
		)
		try:
			doc.save()
		except DuplicateEntryError:
			pass
		except TimestampMismatchError:
			# Handle the update of two sales orders contact details concurrently
			pass

	except Exception:
		doc.log_error(_("Woocommerce Contact Error"))


def get_country_name(code):
	return frappe.db.get_value("Country", dict(code=code), "name")
