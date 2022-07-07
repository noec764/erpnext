import frappe


def get_linked_customers(user):
	contacts = frappe.db.sql(
		"""
		select
			`tabDynamic Link`.link_name,
			`tabDynamic Link`.link_doctype
		from
			`tabContact`, `tabDynamic Link`
		where
			`tabContact`.name=`tabDynamic Link`.parent and `tabContact`.user =%s
		""",
		user,
		as_dict=1,
	)

	return [c.link_name for c in contacts if c.link_doctype == "Customer"], [
		c.link_name for c in contacts if c.link_doctype == "Lead"
	]


@frappe.whitelist()
def get_customer(user):
	customers, dummy = get_linked_customers(user)
	return customers[0] if customers else ""
