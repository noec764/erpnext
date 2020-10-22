# -*- coding: utf-8 -*-
# Copyright (c) 2020, Dokos SAS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class BookingCreditConversion(Document):
	def onload(self):
		self.set_onload('all_items', frappe.get_all("Item", filters={"enable_item_booking": 1}, fields=["item_code", "item_name"]))