import frappe
from erpnext.erpnext_integrations.idempotency import IdempotencyKey, handle_idempotency
from erpnext.erpnext_integrations.doctype.stripe_settings.api.errors import handle_stripe_errors

class StripeWebhookEndpoint:
	def __init__(self, gateway):
		self.gateway = gateway

	@handle_idempotency
	@handle_stripe_errors
	def create(self, url, enabled_events, **kwargs):
		return self.gateway.stripe.WebhookEndpoint.create(
			url=url,
			enabled_events=enabled_events,
			**kwargs
		)

	@handle_stripe_errors
	def retrieve(self, id):
		return self.gateway.stripe.WebhookEndpoint.retrieve(
			id
		)

	@handle_stripe_errors
	def delete(self, id):
		return self.gateway.stripe.WebhookEndpoint.delete(
			id
		)