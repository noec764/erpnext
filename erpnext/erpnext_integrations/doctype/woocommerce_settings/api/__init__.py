from woocommerce import API
import requests

import frappe

class WooCommerceAPI:
	def __init__(self, version="wc/v3", *args, **kwargs):
		self.settings = frappe.get_single("Woocommerce Settings")
		self.version = version
		self.api = API(
			url=self.settings.woocommerce_server_url,
			consumer_key=self.settings.api_consumer_key,
			consumer_secret=self.settings.api_consumer_secret,
			version=version,
			timeout=5000
		)

	def get(self, path, params=None):
		res = self.api.get(path, params=params or {})
		return self.validate_response(res)

	def post(self, path, data):
		res = self.api.post(path, data)
		return self.validate_response(res)

	def put(self, path, data):
		res = self.api.put(path, data)
		return self.validate_response(res)

	def delete(self, path, params=None):
		res = self.api.delete(path, params=params or {})
		return self.validate_response(res)

	def validate_response(self, response):
		response.raise_for_status()
		return response