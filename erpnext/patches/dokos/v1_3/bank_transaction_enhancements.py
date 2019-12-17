import frappe

def execute():
	frappe.reload_doctype("Bank Transaction")
	frappe.reload_doctype("Payment Entry")
	frappe.reload_doctype("Sales Invoice")
	frappe.reload_doctype("Purchase Invoice")
	frappe.reload_doctype("Expense Claim")
	frappe.reload_doctype("Journal Entry")

	for transaction in frappe.get_all("Bank Transaction", filters={"transaction_id": ("!=", "")}, fields=["name", "transaction_id", "reference_number"]):
		if not transaction.reference_number:
			frappe.db.set_value("Bank Transaction", transaction.name, "reference_number", "transaction_id")

	for payment_entry in frappe.get_all("Payment Entry", \
		filters={"docstatus": 1, "clearance_date": ["is", "not set"]}, fields=["paid_amount", "received_amount", "payment_type", "name"]):
		frappe.db.set_value("Payment Entry", payment_entry.name, "unreconciled_amount", \
			payment_entry.paid_amount if payment_entry.payment_type == "Pay" else payment_entry.received_amount)

	for sales_invoice_payment in frappe.get_all("Sales Invoice Payment", \
		filters={"mode_of_payment": ["is", "set"], "clearance_date": ["is", "not set"]}, fields=["sum(amount) as amount", "parent"], group_by="parent"):
		frappe.db.set_value("Sales Invoice", sales_invoice_payment.parent, "unreconciled_amount", \
			sales_invoice_payment.amount)

	for purchase_invoice in frappe.get_all("Purchase Invoice", \
		filters={"docstatus": 1, "clearance_date": ["is", "not set"], "mode_of_payment": ["is", "set"]}, fields=["paid_amount", "name"]):
		frappe.db.set_value("Purchase Invoice", purchase_invoice.name, "unreconciled_amount", \
			purchase_invoice.paid_amount)

	for expense_claim in frappe.get_all("Expense Claim", \
		filters={"docstatus": 1, "clearance_date": ["is", "not set"], "mode_of_payment": ["is", "set"]}, fields=["total_claimed_amount", "name"]):
		frappe.db.set_value("Expense Claim", expense_claim.name, "unreconciled_amount", \
			expense_claim.total_claimed_amount)

	for journal_entry in frappe.get_all("Journal Entry", \
		filters={"docstatus": 1, "clearance_date": ["is", "not set"]}):
		doc = frappe.get_doc("Journal Entry", journal_entry.name)
		doc.update_unreconciled_amount()
