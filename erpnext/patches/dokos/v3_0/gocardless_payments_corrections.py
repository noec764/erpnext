import frappe


def execute():
	for payment in frappe.get_all(
		"Payment Entry",
		filters={
			"payment_request": ("is", "set"),
			"reference_no": ("like", "PM00"),
			"unallocated_amount": (">", 0.0),
		},
	):
		doc = frappe.get_doc("Payment Entry", payment.name)
		if doc.status == "Unreconciled":
			doc.cancel()

			integration_request = frappe.get_doc(
				"Integration Request",
				filters={
					"service_status": "paid_out",
					"service": "GoCardless",
					"reference_docname": doc.payment_request,
				},
			)
			integration_request.retry_webhook()
		else:
			print("Payment amount is incorrect and could not be corrected: ", doc.name)
