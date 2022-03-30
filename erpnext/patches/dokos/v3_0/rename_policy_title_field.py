import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	frappe.reload_doc("hr", "doctype", "Leave Policy")

	try:
		rename_field("Leave Policy", "policy_title", "title")

	except Exception as e:
		if e.args[0] != 1054:
			raise
