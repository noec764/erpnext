import base64
import hashlib
import hmac
import json
from functools import wraps

import frappe
from frappe import _

from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.orders import (
	create_update_order,
)

handler_map = {
	"order.created": create_update_order,
	"order.updated": create_update_order,
}


def woocommerce_webhook(f):
	"""
	Decorator validating a woocommerce Webhook request.
	"""

	@wraps(f)
	def wrapper(*args, **kwargs):
		# Try to get required headers and decode the body of the request.
		woocommerce_settings = frappe.get_doc("Woocommerce Settings")
		sig = base64.b64encode(
			hmac.new(
				woocommerce_settings.secret.encode("utf8"), frappe.request.data, hashlib.sha256
			).digest()
		)

		if (
			frappe.request.data
			and not sig == frappe.get_request_header("X-Wc-Webhook-Signature", "").encode()
		):
			frappe.throw(_("Unverified Webhook Data"))

		return f(*args, **kwargs)

	return wrapper


@frappe.whitelist(allow_guest=True)
def webhooks(*args, **kwargs):
	topic = frappe.local.request.headers.get("X-Wc-Webhook-Topic")
	try:
		data = frappe.parse_json(frappe.safe_decode(frappe.request.data))
	except json.decoder.JSONDecodeError:
		data = frappe.safe_decode(frappe.request.data)

	handler = handler_map.get(topic)
	if handler:
		handler(data)
