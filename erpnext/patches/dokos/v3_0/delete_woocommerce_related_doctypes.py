import frappe


def execute():
	for doctype in (
		"Woocommerce Excluded Order",
		"Woocommerce Shipping Methods",
		"Woocommerce Taxes",
		"Woocommerce Settings",
	):
		frappe.delete_doc_if_exists("DocType", doctype, force=True)
