# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet, get_root_of

from erpnext.portal.utils import update_role_for_users


class CustomerGroup(NestedSet):
	nsm_parent_field = "parent_customer_group"

	def validate(self):
		if not self.parent_customer_group:
			self.parent_customer_group = get_root_of("Customer Group")

	def on_update(self):
		self.validate_name_with_customer()
		super(CustomerGroup, self).on_update()
		self.validate_one_root()
		self.update_user_role()

	def validate_name_with_customer(self):
		if frappe.db.exists("Customer", self.name):
			frappe.msgprint(_("A customer with the same name already exists"), raise_exception=1)

	def update_user_role(self):
		customer_has_role_profile = frappe.get_meta("Supplier").has_field("role_profile_name")
		fields = ["name", "role_profile_name"] if customer_has_role_profile else ["name"]
		for customer in frappe.get_all(
			"Customer", filters={"disabled": 0, "customer_group": self.name}, fields=fields
		):
			frappe.enqueue(
				update_role_for_users,
				doctype="Customer",
				docname=customer.name,
				role_profile=customer.role_profile_name
				if customer_has_role_profile
				else self.role_profile_name,
			)


def get_parent_customer_groups(customer_group):
	lft, rgt = frappe.db.get_value("Customer Group", customer_group, ["lft", "rgt"])

	return frappe.db.sql(
		"""select name from `tabCustomer Group`
		where lft <= %s and rgt >= %s
		order by lft asc""",
		(lft, rgt),
		as_dict=True,
	)


def on_doctype_update():
	frappe.db.add_index("Customer Group", ["lft", "rgt"])
