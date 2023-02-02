# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import nowdate

from frappe.contacts.doctype.contact.contact import invite_user
from erpnext.accounts.doctype.subscription_template.subscription_template import make_subscription

class VenueRegistrationForm(Document):
	def on_submit(self):
		self.create_customer()
		self.create_contact()
		self.create_address()
		self.create_subscription()
		self.create_user()


	def create_user(self):
		invite_user(self.contact)


	def create_contact(self):
		def postprocess(source, target):
			target.append("email_ids", {
				"email_id": self.email,
				"is_primary": 1
			})

			if self.get("phone") or self.get("is_primary_phone"):
				target.append("phone_nos", {
					"phone": self.get("phone") or self.get("is_primary_phone"),
					"is_primary_phone": 1
				})

			if self.get("is_primary_mobile_no"):
				target.append("phone_nos", {
					"phone": self.get("is_primary_mobile_no"),
					"is_primary_mobile_no": 1
				})

			target.append("links", {
				"link_doctype": "Customer",
				"link_name": self.customer
			})

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
			ignore_permissions=True
		)

		mapped_doc.flags.ignore_permissions = True
		mapped_doc.insert()

		self.contact = mapped_doc.name


	def create_address(self):
		def set_missing_values(source, target):
			target.append("links", {
				"link_doctype": "Customer",
				"link_name": self.customer
			})

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
			ignore_permissions=True
		)

		mapped_doc.flags.ignore_permissions = True
		mapped_doc.insert()

		self.address = mapped_doc.name


	def create_customer(self):
		def set_missing_values(source, target):
			target.customer_type = "Company" if self.get("customer_name") else "Individual"
			target.customer_name = self.get("customer_name") or f'{self.first_name} {self.last_name}'
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
			ignore_permissions=True
		)

		mapped_doc.flags.ignore_permissions = True
		mapped_doc.insert()

		self.customer = mapped_doc.name


	def create_subscription(self):
		if self.subscription_template:
			subscription = make_subscription(
				template=self.subscription_template,
				company=self.get("Company") or frappe.db.get_default("Company"),
				customer=self.customer,
				start_date=nowdate(),
				ignore_permissions=True,
			)

			self.subscription = subscription.name


	def on_payment_authorized(self, status=None, reference_no=None):
		if status in ["Authorized", "Completed", "Paid"]:
			self.status = "Payment Method Registered"
			self.submit()

		elif status == "Pending":
			self.status = "Pending"