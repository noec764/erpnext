# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt"


import frappe
from frappe import _
from frappe.utils import cint

from erpnext import get_default_company


def boot_session(bootinfo):
	"""boot session - send website info if guest"""

	# bootinfo.custom_css = frappe.db.get_value("Style Settings", None, "custom_css") or ""

	if frappe.session["user"] != "Guest":
		update_page_info(bootinfo)

		bootinfo.sysdefaults.territory = frappe.db.get_single_value("Selling Settings", "territory")
		bootinfo.sysdefaults.customer_group = frappe.db.get_single_value(
			"Selling Settings", "customer_group"
		)
		bootinfo.sysdefaults.allow_stale = cint(
			frappe.db.get_single_value("Accounts Settings", "allow_stale")
		)
		bootinfo.sysdefaults.over_billing_allowance = frappe.db.get_single_value(
			"Accounts Settings", "over_billing_allowance"
		)

		bootinfo.sysdefaults.quotation_valid_till = cint(
			frappe.db.get_single_value("CRM Settings", "default_valid_till")
		)

		bootinfo.sysdefaults.allow_sales_order_creation_for_expired_quotation = cint(
			frappe.db.get_single_value(
				"Selling Settings", "allow_sales_order_creation_for_expired_quotation"
			)
		)

		bootinfo.sysdefaults.default_payment_days = cint(
			frappe.db.get_single_value("Accounts Settings", "default_payment_days")
		)

		bootinfo.sysdefaults.default_bank_account_name = frappe.db.get_value(
			"Bank Account",
			{"is_default": 1, "is_company_account": 1, "company": get_default_company()},
			"name",
		)

		bootinfo.docs += frappe.db.sql(
			"""select name, default_currency, cost_center, default_selling_terms, default_buying_terms,
			default_letter_head, default_bank_account, enable_perpetual_inventory, country from `tabCompany`""",
			as_dict=1,
			update={"doctype": ":Company"},
		)

		party_account_types = frappe.db.sql(
			""" select name, ifnull(account_type, '') from `tabParty Type`"""
		)
		bootinfo.party_account_types = frappe._dict(party_account_types)

		frappe.cache().hdel("shopping_cart_party", frappe.session.user)


def update_page_info(bootinfo):
	bootinfo.page_info.update(
		{
			"Chart of Accounts": {"title": _("Chart of Accounts"), "route": "Tree/Account"},
			"Chart of Cost Centers": {"title": _("Chart of Cost Centers"), "route": "Tree/Cost Center"},
			"Item Group Tree": {"title": _("Item Group Tree"), "route": "Tree/Item Group"},
			"Customer Group Tree": {"title": _("Customer Group Tree"), "route": "Tree/Customer Group"},
			"Territory Tree": {"title": _("Territory Tree"), "route": "Tree/Territory"},
			"Sales Person Tree": {"title": _("Sales Person Tree"), "route": "Tree/Sales Person"},
		}
	)
