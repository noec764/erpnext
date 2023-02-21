import frappe
from frappe.utils.nestedset import get_root_of

from erpnext.e_commerce.shopping_cart.cart import get_debtors_account, get_shopping_cart_settings


def set_default_role(doc, method):
	"""Set customer, supplier, student, guardian based on email"""
	if frappe.flags.setting_role or frappe.flags.in_migrate:
		return

	roles = frappe.get_roles(doc.name)

	contact_name = frappe.get_value("Contact", dict(email_id=doc.email))
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for link in contact.links:
			frappe.flags.setting_role = True
			if link.link_doctype == "Customer" and "Customer" not in roles:
				doc.add_roles("Customer")
			elif link.link_doctype == "Supplier" and "Supplier" not in roles:
				doc.add_roles("Supplier")


def create_customer_or_supplier():
	"""Based on the default Role (Customer, Supplier), create a Customer / Supplier.
	Called on_session_creation hook.
	"""
	user = frappe.session.user

	if frappe.db.get_value("User", user, "user_type") != "Website User":
		return

	user_roles = frappe.get_roles()
	portal_settings = frappe.get_single("Portal Settings")
	default_role = portal_settings.default_role

	if default_role not in ["Customer", "Supplier"]:
		return

	# create customer / supplier if the user has that role
	if portal_settings.default_role and portal_settings.default_role in user_roles:
		doctype = portal_settings.default_role
	else:
		doctype = None

	if not doctype:
		return

	if party_exists(doctype, user):
		return

	party = frappe.new_doc(doctype)
	fullname = frappe.utils.get_fullname(user)

	if doctype == "Customer":
		cart_settings = get_shopping_cart_settings()

		if cart_settings.enable_checkout:
			debtors_account = get_debtors_account(cart_settings)
		else:
			debtors_account = ""

		party.update(
			{
				"customer_name": fullname,
				"customer_type": "Individual",
				"customer_group": cart_settings.default_customer_group,
				"territory": get_root_of("Territory"),
			}
		)

		if debtors_account:
			party.update({"accounts": [{"company": cart_settings.company, "account": debtors_account}]})
	else:
		party.update(
			{
				"supplier_name": fullname,
				"supplier_group": "All Supplier Groups",
				"supplier_type": "Individual",
			}
		)

	party.flags.ignore_mandatory = True
	party.insert(ignore_permissions=True)

	alternate_doctype = "Customer" if doctype == "Supplier" else "Supplier"

	if party_exists(alternate_doctype, user):
		# if user is both customer and supplier, alter fullname to avoid contact name duplication
		fullname += "-" + doctype

	create_party_contact(doctype, fullname, user, party.name)

	return party


def create_party_contact(doctype, fullname, user, party_name):
	contact = frappe.new_doc("Contact")
	contact.update({"first_name": fullname, "email_id": user})
	contact.append("links", dict(link_doctype=doctype, link_name=party_name))
	contact.append("email_ids", dict(email_id=user, is_primary=True))
	contact.flags.ignore_mandatory = True
	contact.insert(ignore_permissions=True)


def party_exists(doctype, user):
	# check if contact exists against party and if it is linked to the doctype
	contact_name = frappe.db.get_value("Contact", {"email_id": user})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		doctypes = [d.link_doctype for d in contact.links]
		return doctype in doctypes

	return False


def update_role_for_users(doctype, docname, role_profile):
	dynamic_link = frappe.qb.DocType("Dynamic Link")
	contact = frappe.qb.DocType("Contact")
	user = frappe.qb.DocType("User")
	users = (
		frappe.qb.from_(dynamic_link)
		.join(contact)
		.on(
			(contact.name == dynamic_link.parent)
			& (dynamic_link.link_doctype == doctype)
			& (dynamic_link.link_name == docname)
		)
		.join(user)
		.on((contact.email_id == user.name))
		.where(
			(user.enabled == 1)
			& (user.name.notin(frappe.STANDARD_USERS))
			& ((user.role_profile_name != role_profile) | (user.role_profile_name.isnull()))
		)
		.select(user.name)
		.run(as_dict=True, debug=True)
	)

	for user in users:
		user_doc = frappe.get_doc("User", user.name)
		user_doc.role_profile_name = role_profile
		user_doc.flags.ignore_permissions = True

		if not role_profile:
			user_doc.add_default_roles()
		else:
			user_doc.save()


def update_contact_user_roles(doc, method=None):
	if not doc.user:
		return

	if supplier := doc.get_link_for("Supplier"):
		update_linked_user("Supplier", supplier, doc)

	if customer := doc.get_link_for("Customer"):
		update_linked_user("Customer", customer, doc)


def update_linked_user(doctype, docname, doc):
	def get_linked_user(doc):
		return frappe.get_doc("User", doc.user)

	def update_role_profile(user, role_profile):
		if role_profile != user.role_profile_name:
			user.role_profile_name = role_profile
			user.save()

	user = get_linked_user(doc)
	dt_has_field = frappe.get_meta(doctype).has_field("role_profile_name")
	link_group = frappe.db.get_value(doctype, docname, f"{doctype.lower()}_group")
	role_profile = None
	if dt_has_field:
		role_profile = frappe.db.get_value(doctype, docname, "role_profile_name")
	if role_profile:
		update_role_profile(user, role_profile)
	elif role_profile := frappe.db.get_value(f"{doctype} Group", link_group, "role_profile_name"):
		update_role_profile(user, role_profile)
