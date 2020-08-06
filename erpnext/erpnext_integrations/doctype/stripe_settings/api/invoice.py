import frappe
from erpnext.erpnext_integrations.idempotency import IdempotencyKey, handle_idempotency

class StripeInvoice:
	def __init__(self, gateway, payment_request):
		self.gateway = gateway
		self.payment_request = payment_request

	@handle_idempotency
	def create(self, customer, **kwargs):
		from hashlib import sha224
		return self.gateway.stripe.Invoice.create(
			customer=customer,
			idempotency_key=IdempotencyKey("invoice", "create", self.payment_request.name).get(),
			**kwargs
		)

	def retrieve(self, id):
		return self.gateway.stripe.Invoice.retrieve(
			id
		)