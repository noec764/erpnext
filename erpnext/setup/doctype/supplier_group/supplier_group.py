# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe.utils.nestedset import NestedSet, get_root_of

from erpnext.portal.utils import update_role_for_users


class SupplierGroup(NestedSet):
	nsm_parent_field = "parent_supplier_group"

	def validate(self):
		if not self.parent_supplier_group:
			self.parent_supplier_group = get_root_of("Supplier Group")

	def on_update(self):
		NestedSet.on_update(self)
		self.validate_one_root()
		self.update_user_role()

	def on_trash(self):
		NestedSet.validate_if_child_exists(self)
		frappe.utils.nestedset.update_nsm(self)

	def update_user_role(self):
		supplier_has_role_profile = frappe.get_meta("Supplier").has_field("role_profile_name")
		fields = ["name", "role_profile_name"] if supplier_has_role_profile else ["name"]
		for supplier in frappe.get_all(
			"Supplier", filters={"disabled": 0, "supplier_group": self.name}, fields=fields
		):
			frappe.enqueue(
				update_role_for_users,
				doctype="Supplier",
				docname=supplier.name,
				role_profile=supplier.role_profile_name
				if supplier_has_role_profile
				else self.role_profile_name,
			)
