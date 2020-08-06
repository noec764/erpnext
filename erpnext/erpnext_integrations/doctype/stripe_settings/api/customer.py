import frappe
from .idempotency import StripeIdempotencyKey, handle_idempotency

class StripeCustomer:
	def __init__(self, gateway):
		self.gateway = gateway

	def get_or_create(self, customer_id, stripe_id=None):
		if not stripe_id:
			stripe_id = frappe.db.get_value("Integration References", dict(customer=customer_id), "stripe_customer_id")

		if stripe_id:
			customer = self.get(stripe_id)
			if not customer.get("deleted"):
				return customer

		return self.create(customer_id)

	def get(self, stripe_id):
		return self.gateway.stripe.Customer.retrieve(stripe_id)

	@handle_idempotency
	def create(self, customer_id):
		from frappe.contacts.doctype.contact.contact import get_default_contact
		from hashlib import sha224
		metadata = { "customer": customer_id }
		customer_name = frappe.db.get_value("Customer", customer_id, "customer_name")
		contact = get_default_contact("Customer", customer_id)
		contact_email = frappe.db.get_value("Contact", contact, "email_id")

		if customer_name and contact_email:
			stripe_customer = self.gateway.stripe.Customer.create(
				name=customer_name,
				email=contact_email,
				metadata=metadata,
				#idempotency_key=StripeIdempotencyKey("customer", "create", customer_id).get()
			)
			self.register(stripe_customer.get("id"), customer_id)
			return stripe_customer

	def register(self, stripe_id, customer_id):
		if frappe.db.exists("Integration References", dict(customer=customer_id)):
			doc = frappe.get_doc("Integration References", dict(customer=customer_id))
			doc.stripe_customer_id = stripe_id
			doc.stripe_settings = self.gateway.name
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc({
				"doctype": "Integration References",
				"customer": customer_id,
				"stripe_customer_id": stripe_id,
				"stripe_settings": self.gateway.name
			}).insert(ignore_permissions=True)
		frappe.db.commit()

	def update(self, stripe_id, **kwargs):
		return self.gateway.stripe.Customer.modify(
			stripe_id,
			**kwargs
		)

	def delete(self, stripe_id):
		return self.gateway.stripe.Customer.delete(
			stripe_id
		)