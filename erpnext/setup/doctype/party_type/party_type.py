# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import re

import frappe
from frappe import _
from frappe.model.document import Document


class PartyType(Document):
	pass


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_party_type(doctype, txt, searchfield, start, page_len, filters):
	query_filter = {}
	if filters and filters.get("account"):
		account_type = frappe.db.get_value("Account", filters.get("account"), "account_type")
		query_filter = {"account_type": account_type}

	party_types = [d["name"] for d in frappe.get_all("Party Type", filters=query_filter)]

	output = [[v] for v in party_types if re.search(txt + ".*", _(v), re.IGNORECASE)]
	return output
