import frappe


def execute():
	webhooks = frappe.get_all(
		"Integration Request",
		filters={
			"integration_request_service": "GoCardless",
			"service_document": "payments",
			"service_status": "paid_out",
			"creation": (">", "2023-02-01"),
		},
	)
	for wh in webhooks:
		doc = frappe.get_doc("Integration Request", wh.name)
		doc.retry_webhook()

		ref_no = frappe.db.get_value(
			doc.reference_doctype, doc.reference_docname, "transaction_reference"
		)
		if existing_pe := frappe.db.exists("Payment Entry", dict(reference_no=ref_no, status="Pending")):
			frappe.delete_doc("Payment Entry", existing_pe)
