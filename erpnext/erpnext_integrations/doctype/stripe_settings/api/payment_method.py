class StripePaymentMethod:
	def __init__(self, gateway):
		self.gateway = gateway

	def create(self, payment_method_type, **kwargs):
		return self.gateway.stripe.PaymentMethod.create(
			payment_method_type,
			**kwargs
		)

	def retrieve(self, id):
		return self.gateway.stripe.PaymentMethod.retrieve(
			id
		)

	def update(self, id, **kwargs):
		return self.gateway.stripe.PaymentMethod.modify(
			id,
			**kwargs
		)

	def attach(self, id, customer_id):
		return self.gateway.stripe.PaymentMethod.attach(
			id,
			customer=customer_id
		)

	def detach(self, id, customer_id):
		return self.gateway.stripe.PaymentMethod.detach(
			id
		)

	def get_list(self, customer_id, payment_method_type="card", **kwargs):
		return self.gateway.stripe.PaymentMethod.list(
			customer=customer_id,
			type=payment_method_type,
			**kwargs
		)