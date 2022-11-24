import frappe

from erpnext.regional.france.setup import setup


def execute():
	company = frappe.get_all("Company", filters={"country": "France"})
	if not company:
		return

	setup()
