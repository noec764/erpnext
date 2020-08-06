import frappe
from erpnext.erpnext_integrations.idempotency import IdempotencyKey, handle_idempotency

class StripePaymentIntent:
	def __init__(self, gateway, payment_request):
		self.gateway = gateway
		self.payment_request = payment_request

	@handle_idempotency
	def create(self, amount, currency, **kwargs):
		from hashlib import sha224
		return self.gateway.stripe.PaymentIntent.create(
			amount=amount,
			currency=currency,
			idempotency_key=IdempotencyKey("payment_intent", "create", self.payment_request.name).get(),
			**kwargs
		)

	def retrieve(self, id, client_secret):
		return self.gateway.stripe.PaymentIntent.retrieve(
			id,
			client_secret=client_secret
		)

	def update(self, id, **kwargs):
		return self.gateway.stripe.PaymentIntent.modify(
			id,
			**kwargs
		)

	def confirm(self, id, **kwargs):
		return self.gateway.stripe.PaymentIntent.confirm(
			id,
			**kwargs
		)

	def capture(self, id, **kwargs):
		return self.gateway.stripe.PaymentIntent.attach(
			id,
			**kwargs
		)

	def cancel(self, id, **kwargs):
		return self.gateway.stripe.PaymentIntent.detach(
			id,
			**kwargs
		)