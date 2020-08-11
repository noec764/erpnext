import frappe
from erpnext.erpnext_integrations.idempotency import IdempotencyKey, handle_idempotency
from erpnext.erpnext_integrations.doctype.stripe_settings.api.errors import handle_stripe_errors

class StripeInvoiceItem:
	def __init__(self, gateway, payment_request):
		self.gateway = gateway

	@handle_idempotency
	@handle_stripe_errors
	def create(self, customer, **kwargs):
		return self.gateway.stripe.InvoiceItem.create(
			customer=customer,
			idempotency_key=IdempotencyKey("invoice_item", "create", self.payment_request.name).get(),
			**kwargs
		)

	@handle_stripe_errors
	def retrieve(self, id):
		return self.gateway.stripe.Invoice.retrieve(
			id
		)