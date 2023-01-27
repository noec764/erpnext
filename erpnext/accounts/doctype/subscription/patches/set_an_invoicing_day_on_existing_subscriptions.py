import frappe


def execute():
	"""Set an invoicing day on existing subscriptions"""
	for subscription in frappe.get_all(
		"Subscription", filters={"invoicing_day": ("is", "not set"), "status": ("!=", "Cancelled")}
	):
		frappe.get_doc("Subscription", subscription.name).save()
