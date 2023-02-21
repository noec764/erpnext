# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.contacts.doctype.address.address import get_preferred_address
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import nowdate

from erpnext.accounts.doctype.subscription_template.subscription_template import make_subscription


class VenueRegistrationForm(Document):
	def on_submit(self):
		self.create_customer()
		self.create_contact()
		self.create_address()
		self.create_subscription()
		self.create_user()

	def create_user(self):
		contact = frappe.get_doc("Contact", self.contact)

		frappe.flags.mute_messages = True
		user = frappe.get_doc(
			{
				"doctype": "User",
				"first_name": contact.first_name,
				"last_name": contact.last_name,
				"email": contact.email_id,
				"user_type": "Website User",
				"send_welcome_email": 1,
			}
		).insert(ignore_permissions=True)
		frappe.flags.mute_messages = False

		frappe.db.set_value("Contact", self.contact, "user", user.name)

	def create_contact(self):
		if self.contact:
			return

		def postprocess(source, target):
			target.append("email_ids", {"email_id": self.email, "is_primary": 1})

			if self.get("phone") or self.get("is_primary_phone"):
				target.append(
					"phone_nos",
					{"phone": self.get("phone") or self.get("is_primary_phone"), "is_primary_phone": 1},
				)

			if self.get("is_primary_mobile_no"):
				target.append(
					"phone_nos", {"phone": self.get("is_primary_mobile_no"), "is_primary_mobile_no": 1}
				)

			target.append("links", {"link_doctype": "Customer", "link_name": self.customer})

		mapped_doc = get_mapped_doc(
			self.doctype,
			self.name,
			{
				self.doctype: {
					"doctype": "Contact",
					"field_no_map": ["status"],
				},
			},
			postprocess=postprocess,
			ignore_permissions=True,
		)

		mapped_doc.flags.ignore_permissions = True
		mapped_doc.insert()

		self.db_set("contact", mapped_doc.name)

	def create_address(self):
		if self.address:
			return

		def set_missing_values(source, target):
			target.append("links", {"link_doctype": "Customer", "link_name": self.customer})
			target.is_primary_address = 1

		mapped_doc = get_mapped_doc(
			self.doctype,
			self.name,
			{
				self.doctype: {
					"doctype": "Address",
					"field_no_map": ["status"],
				},
			},
			postprocess=set_missing_values,
			ignore_permissions=True,
		)

		mapped_doc.flags.ignore_permissions = True
		mapped_doc.insert()

		self.db_set("address", mapped_doc.name)

	def create_customer(self):
		if self.customer:
			return

		def set_missing_values(source, target):
			target.customer_type = "Company" if self.get("customer_name") else "Individual"
			target.customer_name = self.get("customer_name") or f"{self.first_name} {self.last_name}"
			target.customer_group = frappe.db.get_default("Customer Group")
			target.territory = frappe.db.get_default("Territory")

		mapped_doc = get_mapped_doc(
			self.doctype,
			self.name,
			{
				self.doctype: {
					"doctype": "Customer",
					"field_no_map": ["status"],
				},
			},
			None,
			set_missing_values,
			ignore_permissions=True,
		)

		mapped_doc.flags.ignore_permissions = True
		mapped_doc.insert()

		self.db_set("customer", mapped_doc.name)

	def create_subscription(self):
		if self.subscription:
			return

		if self.subscription_template:
			subscription = make_subscription(
				template=self.subscription_template,
				company=self.get("Company") or frappe.db.get_default("Company"),
				customer=self.customer,
				start_date=nowdate(),
				ignore_permissions=True,
			)

			self.db_set("subscription", subscription.name)

	def set_as_completed_and_submit(self):
		self.status = "Completed"
		self.flags.ignore_permissions = True
		self.submit()

	def on_payment_authorized(self, status=None, reference_no=None):
		if reference_no:
			self.db_set("payment_reference", reference_no)

		if status in ["Authorized", "Completed", "Paid", "Payment Method Registered"]:
			if self.docstatus == 0:
				self.set_as_completed_and_submit()

		elif status == "Pending" and self.status != "Completed":
			self.status = "Pending"
			self.flags.ignore_permissions = True
			self.save()

	def on_webform_save(self, webform):
		if self.flags.in_payment_webform:
			self.db_set("status", "Initiated")
			self.create_customer()
			self.save()  # This document will be fetched again in the payment gateway
		else:
			self.set_as_completed_and_submit()


def get_webform_context(context):
	if frappe.session.user == "Guest":
		return

	existing_values = frappe._dict()
	if contact := frappe.db.get_value("Contact", dict(email_id=frappe.session.user), "name"):
		contact_doc = frappe.get_doc("Contact", contact)
		if customer := contact_doc.get_link_for("Customer"):
			customer_doc = frappe.get_doc("Customer", customer)
			existing_values.update(customer_doc.as_dict())
			if address := get_preferred_address("Customer", customer):
				address_doc = frappe.get_doc("Address", address)
				existing_values.update(address_doc.as_dict())

		existing_values.update(contact_doc.as_dict())

	meta = frappe.get_meta(context.doc_type)
	for field in meta.fields:
		if field.fieldname in existing_values:
			context.reference_doc[field.fieldname] = existing_values[field.fieldname]
