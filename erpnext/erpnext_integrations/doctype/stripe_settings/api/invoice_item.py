import frappe
from .idempotency import StripeIdempotencyKey, handle_idempotency

class StripeInvoiceItem:
	def __init__(self, gateway, payment_request):
		self.gateway = gateway

	@handle_idempotency
	def create(self, customer, **kwargs):
		return self.gateway.stripe.InvoiceItem.create(
			customer=customer,
			idempotency_key=StripeIdempotencyKey("invoice_item", "create", self.payment_request.name).get(),
			**kwargs
		)

	def retrieve(self, id):
		return self.gateway.stripe.Invoice.retrieve(
			id
		)