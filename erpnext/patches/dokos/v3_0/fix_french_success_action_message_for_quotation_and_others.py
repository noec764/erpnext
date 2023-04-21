import frappe


def execute():
	"""Fix default Success Action for French users of Quotation and other doctypes"""

	from erpnext.setup.default_success_action import doctype_list

	for doctype in doctype_list:
		old_msg = "{0} a été envoyé avec succès".format(frappe._(doctype))

		filters = {
			"ref_doctype": doctype,
			"first_success_message": old_msg,
			"message": old_msg,
		}
		for doc in frappe.get_all("Success Action", filters=filters):
			print("Updating Success Action for {0}: {1}".format(doctype, doc.name))
			new_msg = "{0} a été validé avec succès".format(frappe._(doctype))
			doc = frappe.get_doc("Success Action", doc.name)
			doc.first_success_message = new_msg
			doc.message = new_msg
			doc.save()
