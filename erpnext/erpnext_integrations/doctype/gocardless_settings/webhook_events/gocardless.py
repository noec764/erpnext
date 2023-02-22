import json

import frappe
from frappe import _

from erpnext.erpnext_integrations.doctype.gocardless_settings.api import (
	GoCardlessMandates,
	GoCardlessPayments,
)

MANDATES_STATUS = {
	"customer_approval_granted": "Pending Customer Approval",
	"customer_approval_skipped": "Pending Submission",
	"active": "Active",
	"cancelled": "Cancelled",
	"failed": "Failed",
	"transferred": "Submitted",
	"expired": "Expired",
	"submitted": "Submitted",
	"resubmission_requested": "Pending Submission",
	"reinstated": "Active",
	"replaced": "Cancelled",
	"created": "Pending Submission",
}

PAYMENTS_STATUS = {
	"created": "Pending",
	"submitted": "Pending",
	"confirmed": "Paid",
	"cancelled": "Failed",
	"failed": "Failed",
	"paid_out": "Paid",
}


class GoCardlessWebhookHandler:
	def __init__(self, **kwargs):
		self.integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))
		self.integration_request.db_set("error", None)
		self.data = json.loads(self.integration_request.get("data"))
		self.payment = self.data.get("links", {}).get("payment")
		self.metadata = {}
		self.gocardless_settings = frappe.get_doc(
			"GoCardless Settings", self.integration_request.payment_gateway_controller
		)

		if self.integration_request.service_document == "payments":
			self.get_reference_documents()

		self.integration_request.load_from_db()
		self.handle_webhook()

	def get_reference_documents(self):
		gc_payment = GoCardlessPayments(self.gocardless_settings).get(self.payment)
		self.metadata = getattr(gc_payment, "metadata", {})

		for k in ("reference_doctype", "reference_docname", "reference_name"):
			if k in self.metadata:
				key = "reference_docname" if k == "reference_name" else k
				self.integration_request.db_set(key, self.metadata[k])

		# For compatibility
		if "payment_request" in self.metadata:
			self.integration_request.db_set("reference_doctype", "Payment Request")
			self.integration_request.db_set("reference_docname", self.metadata["payment_request"])

	def handle_webhook(self):
		action = self.data.get("action")
		service = self.integration_request.service_document

		if service == "payments":
			self.handle_payments(action)

		elif service == "mandates":
			self.handle_mandates(action)

	def handle_payments(self, action):
		if action not in PAYMENTS_STATUS:
			return self.integration_request.handle_failure(
				response={"message": _("This type of event is not handled")}, status="Not Handled"
			)

		elif not (
			self.integration_request.reference_doctype and self.integration_request.reference_docname
		):
			return self.integration_request.handle_failure(
				response={"message": _("This event contains not metadata")}, status="Failed"
			)

		elif not frappe.db.exists(
			self.integration_request.reference_doctype, self.integration_request.reference_docname
		):
			return self.integration_request.handle_failure(
				response={"message": _("The reference document does not exist")}, status="Failed"
			)

		try:
			reference_document = frappe.get_doc(
				self.integration_request.reference_doctype, self.integration_request.reference_docname
			)
			response = reference_document.run_method(
				"on_payment_authorized", status=PAYMENTS_STATUS[action], reference_no=self.payment
			)

			self.integration_request.handle_success(response={"message": response})

		except Exception:
			self.integration_request.handle_failure(
				response={"message": frappe.get_traceback()}, status="Failed"
			)

	def handle_mandates(self, action):
		if action not in MANDATES_STATUS:
			return self.integration_request.handle_failure(
				response={"message": _("This type of event is not handled")}, status="Not Handled"
			)

		try:
			response = self.change_mandate_status()
			self.integration_request.handle_success(response={"message": response})

		except Exception:
			self.integration_request.handle_failure(
				response={"message": frappe.get_traceback()}, status="Failed"
			)

	def change_mandate_status(self):
		mandate = self.data.get("links", {}).get("mandate")
		if not frappe.db.exists("Sepa Mandate", mandate):
			self.create_mandate(mandate)

		sepa_mandate = self.set_mandate_status(mandate, MANDATES_STATUS.get(self.data.get("action")))

		self.integration_request.db_set("reference_doctype", "Sepa Mandate")
		self.integration_request.db_set("reference_docname", sepa_mandate)

		return _("Mandate updated successfully")

	def create_mandate(self, mandate):
		gc_mandate = GoCardlessMandates(self.gocardless_settings).get(mandate) or {}
		gocardless_customer = gc_mandate.links.customer
		customer = frappe.db.get_value(
			"Integration References", {"gocardless_customer_id": gocardless_customer}, ["customer"]
		)

		if customer:
			GoCardlessMandates(self.gocardless_settings).register(mandate, customer)

	def set_mandate_status(self, mandate, status):
		doc = frappe.get_doc("Sepa Mandate", mandate)
		if doc.status != status:
			doc.status = status
			doc.flags.ignore_permissions = True
			doc.save()

		return doc.name
