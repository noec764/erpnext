# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import set_name_by_naming_series, set_name_from_naming_options


class Campaign(Document):
	def autoname(self):
		campaign_naming = frappe.defaults.get_global_default("campaign_naming_by")
		if campaign_naming == "Campaign Name":
			self.name = self.campaign_name
		elif campaign_naming == "Naming Series":
			set_name_by_naming_series(self)
		else:
			self.name = set_name_from_naming_options(frappe.get_meta(self.doctype).autoname, self)
