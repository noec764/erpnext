# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.model.document import Document
from frappe.utils import cint

from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.orders import (
	WooCommerceShippingMethodsAPI,
	WooCommerceTaxesAPI,
	sync_orders,
)
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.products import (
	sync_items,
	sync_products,
)
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.webhooks import (
	create_webhooks,
	delete_webhooks,
)


class WoocommerceSettings(Document):
	def validate(self):
		self.validate_settings()
		self.create_delete_custom_fields()
		self.create_webhook_url()

	def on_update(self):
		self.create_webhooks()

	def create_delete_custom_fields(self):
		if self.enable_sync:
			# create
			for doctype in ["Customer", "Sales Order", "Item", "Address", "Item Attribute", "Item Booking"]:
				fields = [
					dict(
						fieldname="woocommerce_id",
						label="Woocommerce ID",
						fieldtype="Data",
						read_only=1,
						print_hide=1,
						translatable=0,
					)
				]
				for df in fields:
					create_custom_field(doctype, df)

			for doctype in ["Customer", "Address"]:
				fields = [
					dict(
						fieldname="woocommerce_email",
						label="Woocommerce Email",
						fieldtype="Data",
						read_only=1,
						print_hide=1,
						translatable=0,
					)
				]
				for df in fields:
					create_custom_field(doctype, df)

			for doctype in ["Item"]:
				fields = [
					dict(
						fieldname="last_woocommerce_sync",
						label="Last Woocommerce Sync",
						fieldtype="Datetime",
						hidden=1,
						print_hide=1,
					),
					dict(
						fieldname="sync_with_woocommerce",
						label="Sync with Woocommerce",
						fieldtype="Check",
						insert_after="is_stock_item",
						print_hide=1,
					),
				]
				for df in fields:
					create_custom_field(doctype, df)

			for doctype in ["Sales Order"]:
				fields = [
					dict(
						fieldname="woocommerce_number",
						label="Woocommerce Number",
						fieldtype="Data",
						read_only=1,
						translatable=0,
					),
				]
				for df in fields:
					create_custom_field(doctype, df)

	def validate_settings(self):
		if self.enable_sync:
			if not self.secret:
				self.set("secret", frappe.generate_hash())

			if not self.woocommerce_server_url:
				frappe.throw(_("Please enter Woocommerce Server URL"))

			if not self.api_consumer_key:
				frappe.throw(_("Please enter API Consumer Key"))

			if not self.api_consumer_secret:
				frappe.throw(_("Please enter API Consumer Secret"))

	def create_webhook_url(self):
		endpoint = "/api/method/erpnext.erpnext_integrations.connectors.woocommerce_connection.webhooks"

		try:
			url = frappe.request.url
		except RuntimeError:
			# for CI Test to work
			url = "http://localhost:8000"

		server_url = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(url))

		delivery_url = server_url + endpoint
		self.endpoint = delivery_url

	def create_webhooks(self):
		if self.enable_sync and self.endpoint:
			create_webhooks()
		elif (
			not self.enable_sync
			and self.woocommerce_server_url
			and self.api_consumer_key
			and self.api_consumer_secret
		):
			delete_webhooks()


@frappe.whitelist()
def generate_secret():
	woocommerce_settings = frappe.get_doc("Woocommerce Settings")
	woocommerce_settings.secret = frappe.generate_hash()
	woocommerce_settings.save()


@frappe.whitelist()
def get_series():
	return {
		"sales_order_series": frappe.get_meta("Sales Order").get_options("naming_series"),
	}


@frappe.whitelist()
def get_taxes():
	wc_api = WooCommerceTaxesAPI()
	taxes = wc_api.get_taxes()
	return taxes


@frappe.whitelist()
def get_shipping_methods():
	wc_api = WooCommerceShippingMethodsAPI()
	shipping_methods = wc_api.get_shipping_methods(params={"per_page": 100})
	return shipping_methods


@frappe.whitelist()
def get_products():
	sync_items()


def sync_woocommerce():
	if cint(frappe.db.get_single_value("Woocommerce Settings", "enable_sync")):
		if cint(frappe.db.get_single_value("Woocommerce Settings", "sync_products")):
			sync_products()
		else:
			sync_items()

		sync_orders()
