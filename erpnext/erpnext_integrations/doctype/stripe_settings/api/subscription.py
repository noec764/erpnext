import frappe
from .idempotency import StripeIdempotencyKey, handle_idempotency

class StripeSubscription:
	def __init__(self, gateway, subscription_id):
		self.gateway = gateway
		self.subscription = subscription_id

	@handle_idempotency
	def create(self, customer, **kwargs):
		from hashlib import sha224
		return self.gateway.stripe.Subscription.create(
			customer=customer,
			idempotency_key=StripeIdempotencyKey("subscription", "create", self.subscription).get(),
			**kwargs
		)

	def retrieve(self, id):
		return self.gateway.stripe.Subscription.retrieve(
			id
		)

	def cancel(self, id, invoice_now=False, prorate=False):
		return self.gateway.stripe.Subscription.delete(
			id,
			invoice_now=invoice_now,
			prorate=prorate
		)