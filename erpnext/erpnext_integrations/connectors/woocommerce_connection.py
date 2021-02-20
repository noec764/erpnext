
from __future__ import unicode_literals
import frappe, base64, hashlib, hmac, json
from frappe import _

handler_map = {}

def woocommerce_webhook(f):
	"""
	Decorator checking and validating a woocommerce Webhook request.
	"""
	def _hmac_is_valid(body, secret, hmac_to_verify):
		secret = str(secret)
		hash = hmac.new(secret, body, hashlib.sha256)
		hmac_calculated = base64.b64encode(hash.digest())
		return hmac_calculated == hmac_to_verify

	@wraps(f)
	def wrapper(*args, **kwargs):
		# Try to get required headers and decode the body of the request.
		try:
			webhook_topic = frappe.local.request.headers.get('X-woocommerce-Topic')
			webhook_hmac = frappe.local.request.headers.get('X-woocommerce-Hmac-Sha256')
			webhook_data = frappe._dict(frappe.parse_json(frappe.local.request.get_data()))
		except:
			raise ValidationError()

		# Verify the HMAC.
		woocommerce_settings = frappe.get_doc("Woocommerce Settings")
		if not _hmac_is_valid(frappe.local.request.get_data(), woocommerce_settings.secret, webhook_hmac):
			raise AuthenticationError()

			# Otherwise, set properties on the request object and return.
		frappe.local.request.webhook_topic = webhook_topic
		frappe.local.request.webhook_data  = webhook_data
		kwargs.pop('cmd')

		return f(*args, **kwargs)
	return wrapper

@frappe.whitelist(allow_guest=True)
def webhooks(*args, **kwargs):
	topic = frappe.local.request.webhook_topic
	data = frappe.local.request.webhook_data
	handler = handler_map.get(topic)
	if handler:
		handler(data)
