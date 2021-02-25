import json
import frappe

from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI

class WooCommerceWebhooks(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceWebhooks, self).__init__(version, args, kwargs)

	def create(self, data):
		return self.post("webhooks", data).json()

def create_webhooks():
	wc_api = WooCommerceWebhooks()

	for topic, name in {
		"coupon.created": "Coupon Created",
		"coupon.updated": "Coupon Updated",
		"coupon.deleted": "Coupon Deleted",
		"coupon.restored": "Coupon Restored",
		"customer.created": "Customer Created",
		"customer.updated": "Customer Updated",
		"customer.deleted": "Customer Deleted",
		"customer.restored": "Customer Restored",
		"order.created": "Order Created",
		"order.updated": "Order Updated",
		"order.deleted": "Order Deleted",
		"order.restored": "Order Restored",
		"product.created": "Product Created",
		"product.updated": "Product Updated",
		"product.deleted": "Product Deleted",
		"product.restored": "Product Restored",
	}.items():
		wc_api.create({
			"topic": topic,
			"name": name,
			"delivery_url": wc_api.settings.endpoint,
			"secret": wc_api.settings.secret
		})

def delete_webhooks():
	wc_api = WooCommerceWebhooks()

	webhooks = wc_api.get("webhooks", params={"per_page": 100}).json()
	for webhook in webhooks:
		res = wc_api.delete(f"webhooks/{webhook['id']}", params={"force": True}).json()