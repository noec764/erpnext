# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.nestedset import get_root_of
from frappe.model.document import Document
from six.moves.urllib.parse import urlparse
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.orders import WooCommerceTaxes, WooCommerceShippingMethods, sync_orders
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.products import sync_items, sync_products
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.webhooks import create_webhooks, delete_webhooks

class WoocommerceSettings(Document):
	def validate(self):
		self.validate_settings()
		self.create_delete_custom_fields()
		self.create_webhook_url()
		self.create_webhooks()

	def create_delete_custom_fields(self):
		if self.enable_sync:
			custom_fields = {}
			# create
			for doctype in ["Customer", "Sales Order", "Item", "Address", "Item Attribute"]:
				fields = [
					dict(fieldname='woocommerce_id', label='Woocommerce ID', fieldtype='Data', read_only=1, print_hide=1, translatable=0),
					dict(fieldname='last_woocommerce_sync', label='Last Woocommerce Sync', fieldtype='Datetime', hidden=1, print_hide=1)
				]
				for df in fields:
					create_custom_field(doctype, df)

			for doctype in ["Customer", "Address"]:
				fields = [
					dict(fieldname='woocommerce_email', label='Woocommerce Email', fieldtype='Data', read_only=1, print_hide=1)
				]
				for df in fields:
					create_custom_field(doctype, df)

			for doctype in ["Item"]:
				fields = [
					dict(fieldname='sync_with_woocommerce', label='Sync with Woocommerce', fieldtype='Check', insert_after='is_stock_item', print_hide=1)
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

		server_url = '{uri.scheme}://{uri.netloc}'.format(
			uri=urlparse(url)
		)

		delivery_url = server_url + endpoint
		self.endpoint = delivery_url

	def create_webhooks(self):
		if self.enable_sync:
			create_webhooks()
		else:
			delete_webhooks()


@frappe.whitelist()
def generate_secret():
	woocommerce_settings = frappe.get_doc("Woocommerce Settings")
	woocommerce_settings.secret = frappe.generate_hash()
	woocommerce_settings.save()

@frappe.whitelist()
def get_series():
	return {
		"sales_order_series" : frappe.get_meta("Sales Order").get_options("naming_series"),
	}

@frappe.whitelist()
def get_taxes():
	wc_api = WooCommerceTaxes()
	taxes = wc_api.get_taxes()
	return taxes

@frappe.whitelist()
def get_shipping_methods():
	wc_api = WooCommerceShippingMethods()
	shipping_methods = wc_api.get_shipping_methods()
	return shipping_methods

@frappe.whitelist()
def get_products():
	sync_items()

def sync_woocommerce():
	if cint(frappe.get_single_value("Woocommerce Settings", "enable_sync")):
		sync_products()
		sync_orders()