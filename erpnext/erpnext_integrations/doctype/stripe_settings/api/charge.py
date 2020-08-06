import frappe

class StripeCharge:
	def __init__(self, gateway):
		self.gateway = gateway

	def retrieve(self, id):
		return self.gateway.stripe.Charge.retrieve(
			id,
			expand=["balance_transaction"]
		)