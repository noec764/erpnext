# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from urllib.parse import quote

import frappe
import frappe.defaults
from frappe import _, throw
from frappe.contacts.doctype.address.address import get_address_display, get_condensed_address
from frappe.contacts.doctype.contact.contact import get_contact_name
from frappe.utils import cint, cstr, flt, get_fullname
from frappe.utils.nestedset import get_root_of

from erpnext.accounts.utils import get_account_name
from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import (
	get_shopping_cart_settings,
)
from erpnext.utilities.product import get_web_item_qty_in_stock


class WebsitePriceListMissingError(frappe.ValidationError):
	pass


def set_cart_count(quotation=None):
	if cint(get_shopping_cart_settings().enabled):
		if not quotation:
			quotation = _get_cart_quotation()
		cart_count = cstr(cint(quotation.get("total_qty")))

		if hasattr(frappe.local, "cookie_manager"):
			frappe.local.cookie_manager.set_cookie("cart_count", cart_count)


@frappe.whitelist()
def get_cart_quotation(doc=None):
	party = get_party()

	if not doc:
		quotation = _get_cart_quotation(party)
		doc = quotation
		set_cart_count(quotation)

	addresses = get_address_docs(party=party)

	if not doc.customer_address and addresses:
		update_cart_address("billing", addresses[0].name, no_render=True)

	route = get_current_route()

	context = {
		"route": route,
		"doc": decorate_quotation_doc(doc),
		"shipping_addresses": get_shipping_addresses(party, doc),
		"billing_addresses": get_billing_addresses(party, doc),
		"cart_settings": get_shopping_cart_settings(),
		"shipping_rules": get_shipping_rules(doc),
		"link_title_doctypes": frappe.boot.get_link_title_doctypes(),
		"shipping_estimates": [],
		"cart_address_fields": [],
	}

	if route == "checkout":
		add_context_for_checkout(doc, context)

	if route == "cart":
		if any(item.is_free_item and item.item_booking for item in doc.items):
			from erpnext.venue.doctype.booking_credit.booking_credit import get_balance
			from erpnext.venue.utils import get_customer

			context["credits_balance"] = get_balance(get_customer())

	add_context_for_custom_blocks(doc, route, context)

	return context


def add_context_for_custom_blocks(doc, route, context):
	custom_blocks = context["cart_settings"].get("custom_cart_blocks") or []
	custom_blocks_by_position: dict[str, list] = {}

	for block in custom_blocks:
		if route == "cart" and not block.get("show_on_cart"):
			continue
		if route == "checkout" and not block.get("show_on_checkout"):
			continue

		template = block.get("web_template")
		values = block.get("web_template_values") or {}
		values = frappe.parse_json(values)
		values["doc"] = doc

		instanced_block = {
			"position": block.get("position") or "Last",
			"show_on_cart": block.get("show_on_cart") or False,
			"show_on_checkout": block.get("show_on_checkout") or False,
			"css_class": block.get("css_class") or "",
			"template": template,
			"values": values,
			"add_top_padding": 0,
			"add_bottom_padding": 0,
			"add_container": 0,
		}

		block_position = str(instanced_block.get("position"))
		if block_position not in custom_blocks_by_position:
			custom_blocks_by_position[block_position] = []
		custom_blocks_by_position[block_position].append(instanced_block)

	context["custom_cart_blocks"] = custom_blocks_by_position


def add_context_for_checkout(doc, context):
	context["cart_address_fields"] = get_custom_address_fields(context["cart_settings"])

	if shipping_rules := context["shipping_rules"]:
		context["shipping_estimates"] = get_estimates_for_shipping(doc, shipping_rules)

	if doc.shipping_rule:
		context["available_pickup_locations"] = [
			{
				"value": address_name,
				"label": get_condensed_address(frappe.get_doc("Address", address_name)),
				**({"selected": True} if address_name == doc.shipping_address_name else {}),
			}
			for address_name in frappe.get_all(
				"Pick-up Location",
				pluck="address_name",
				filters={
					"enabled": 1,
					"parent": doc.shipping_rule,
					"parenttype": "Shipping Rule",
				},
			)
		]


def get_current_route():
	route = ""
	if hasattr(frappe.local, "request"):
		route = frappe.local.request.path.strip("/ ")
		if not route:
			route = frappe.local.request.environ.get("HTTP_REFERER")
			route = route.split("/")[-1] if route else None
	return route


@frappe.whitelist()
def get_shipping_addresses(party=None, doc=None):
	if not party:
		party = get_party()
	addresses = get_address_docs(party=party)

	if doc and doc.shipping_address_name:
		if not next((x for x in addresses if x.name == doc.shipping_address_name), None):
			a = frappe.get_doc("Address", doc.shipping_address_name)
			a.display = get_address_display(a.as_dict())
			addresses.append(a)

	return [
		{"name": address.name, "title": address.address_title, "display": address.display}
		for address in addresses
		if address.address_type == "Shipping" or (doc and address.name == doc.shipping_address_name)
	]


@frappe.whitelist()
def get_billing_addresses(party=None, doc=None):
	if not party:
		party = get_party()
	addresses = get_address_docs(party=party)

	if doc and doc.customer_address:
		if not next((x for x in addresses if x.name == doc.customer_address), None):
			a = frappe.get_doc("Address", doc.customer_address)
			a.display = get_address_display(a.as_dict())
			addresses.append(a)

	return [
		{"name": address.name, "title": address.address_title, "display": address.display}
		for address in addresses
		if address.address_type == "Billing" or (doc and address.name == doc.customer_address)
	]


@frappe.whitelist()
def place_order():
	quotation = _get_cart_quotation()
	cart_settings = get_shopping_cart_settings()  # ["company", "allow_items_not_in_stock"]

	quotation.company = cart_settings.company

	validate_shipping_rule(quotation, cart_settings, throw_exception=True)

	quotation.flags.ignore_permissions = True
	quotation.submit()

	if quotation.quotation_to == "Lead" and quotation.party_name:
		# company used to create customer accounts
		frappe.defaults.set_user_default("company", quotation.company)

	if not (quotation.shipping_address_name or quotation.customer_address):
		frappe.throw(_("Set Shipping Address or Billing Address"))

	from erpnext.selling.doctype.quotation.quotation import _make_sales_order

	sales_order = frappe.get_doc(_make_sales_order(quotation.name, ignore_permissions=True))
	sales_order.payment_schedule = []

	if not cint(cart_settings.allow_items_not_in_stock):
		for item in sales_order.get("items"):
			item.warehouse = frappe.db.get_value(
				"Website Item", {"item_code": item.item_code}, "website_warehouse"
			)
			is_stock_item = frappe.db.get_value("Item", item.item_code, "is_stock_item")

			if is_stock_item:
				item_stock = get_web_item_qty_in_stock(item.item_code, "website_warehouse")
				if not cint(item_stock.in_stock):
					throw(_("{0} Not in Stock").format(item.item_code))
				if item.qty > item_stock.stock_qty[0][0]:
					throw(_("Only {0} in Stock for item {1}").format(item_stock.stock_qty[0][0], item.item_code))

	sales_order.flags.ignore_permissions = True
	sales_order.insert()
	sales_order.submit()

	if hasattr(frappe.local, "cookie_manager"):
		frappe.local.cookie_manager.delete_cookie("cart_count")

	redirect_url = f"/orders/{quote(sales_order.name)}"
	if (
		cart_settings.payment_gateway_account
		and not cart_settings.no_payment_gateway
		and (flt(sales_order.rounded_total or sales_order.grand_total) - flt(sales_order.advance_paid))
		> 0.0
	):
		from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request

		pr = make_payment_request(
			dn=sales_order.name,
			dt=sales_order.doctype,
			submit_doc=1,
			order_type="Shopping Cart",
			return_doc=1,
		)

		redirect_url = pr.get_payment_url(pr.payment_gateway)

	return redirect_url


@frappe.whitelist()
def request_for_quotation():
	quotation = _get_cart_quotation()
	quotation.flags.ignore_permissions = True

	if get_shopping_cart_settings().save_quotations_as_draft:
		quotation.save()
	else:
		quotation.submit()

	return quotation.name


@frappe.whitelist()
def update_cart(item_code, qty, additional_notes=None, with_items=False, uom=None, booking=None):
	quotation = _get_cart_quotation()

	empty_card = False
	qty = flt(qty)

	if qty == 0:
		if booking:
			quotation_items = quotation.get("items", filters={"item_booking": ["!=", booking]})
			frappe.delete_doc("Item Booking", booking, ignore_permissions=True, force=True)
		else:
			quotation_items = quotation.get("items", filters={"item_code": ["!=", item_code]})
			quotation_items += quotation.get(
				"items", filters={"item_code": ["=", item_code], "item_booking": ["!=", None]}
			)

		if quotation_items:
			quotation.set("items", quotation_items)
		else:
			empty_card = True

	else:
		filters = {}
		_keys = {"item_code": item_code, "uom": uom, "item_booking": booking}
		for key in _keys:
			if _keys[key]:
				filters.update({key: _keys[key]})

		quotation_items = quotation.get("items", filters)

		if not quotation_items:
			quotation.append(
				"items",
				{
					"doctype": "Quotation Item",
					"item_code": item_code,
					"qty": qty,
					"additional_notes": additional_notes,
					"uom": uom,
					"item_booking": booking,
				},
			)
		else:
			quotation_items[0].qty = qty
			quotation_items[0].additional_notes = additional_notes
			if uom:
				quotation_items[0].uom = uom

	apply_cart_settings(quotation=quotation)

	quotation.flags.ignore_permissions = True
	quotation.payment_schedule = []
	if not empty_card:
		quotation.save()
	else:
		quotation.delete()
		quotation = None

	set_cart_count(quotation)

	if cint(with_items):
		return render_quotation(get_cart_quotation(quotation))
	else:
		return {"name": quotation.name}


def render_quotation(context=None):
	if not context:
		context = get_cart_quotation()

	out = {
		"summary": frappe.render_template("templates/includes/cart/cart_summary.html", context),
		"available_pickup_locations": context.get("available_pickup_locations"),
		"_render": True,
	}

	route = context.get("route")

	if route == "cart":
		out["items"] = frappe.render_template("templates/includes/cart/cart_items.html", context)
		out["total"] = frappe.render_template("templates/includes/cart/cart_items_total.html", context)

	if route == "checkout":
		out["cart_address"] = frappe.render_template(
			"templates/includes/cart/cart_address.html", context
		)

	return out


@frappe.whitelist()
def add_new_address(doc):
	doc = frappe.parse_json(doc)
	doc.update({"doctype": "Address"})
	address = frappe.get_doc(doc)
	address.save(ignore_permissions=True)

	return address


@frappe.whitelist()
def get_customer_address():
	# This method is true if an address is already available or false if no address has been entered by the customer yet
	quotation = _get_cart_quotation()
	return quotation.get("customer_address")


@frappe.whitelist(allow_guest=True)
def create_lead_for_item_inquiry(lead, subject, message, item=None):
	lead = frappe.parse_json(lead)
	lead_doc = frappe.new_doc("Lead")
	for fieldname in ("lead_name", "company_name", "email_id", "phone"):
		lead_doc.set(fieldname, lead.get(fieldname))

	lead_doc.set("lead_owner", "")

	if not frappe.db.exists("Lead Source", "Product Inquiry"):
		frappe.get_doc({"doctype": "Lead Source", "source_name": "Product Inquiry"}).insert(
			ignore_permissions=True
		)

	lead_doc.set("source", "Product Inquiry")

	try:
		lead_doc.save(ignore_permissions=True)
	except frappe.exceptions.DuplicateEntryError:
		frappe.clear_messages()
		lead_doc = frappe.get_doc("Lead", {"email_id": lead["email_id"]})

	item_code_and_name = ""
	if item:
		item_name = frappe.db.get_value("Item", item, "item_name")
		item_code_and_name = f'<h6>{_("Item")}: {item_name or ""} ({item})</h6>'

	lead_doc.add_comment(
		"Comment",
		text=f"""
		<div>
			<h5>{subject}</h5>
			{item_code_and_name}
			<p>{message}</p>
		</div>
	""",
	)

	return lead_doc


@frappe.whitelist()
def get_terms_and_conditions(terms_name):
	return frappe.db.get_value("Terms and Conditions", terms_name, "terms")


@frappe.whitelist()
def update_cart_address(
	address_type,
	address_name,
	billing_address_is_same_as_shipping_address: str = "0",
	no_render=False,
):
	billing_address_is_same_as_shipping_address = cint(billing_address_is_same_as_shipping_address)

	quotation = _get_cart_quotation()
	address_doc = frappe.get_doc("Address", address_name).as_dict()
	address_display = get_address_display(address_doc)

	shipping_addresses = get_shipping_addresses()
	billing_addresses = get_billing_addresses()

	if address_type.lower() == "billing":
		quotation.customer_address = address_name
		quotation.address_display = address_display
		quotation.shipping_address_name = quotation.shipping_address_name or address_name
		address_doc = next((doc for doc in shipping_addresses if doc["name"] == address_name), None)
	elif address_type.lower() == "shipping":
		quotation.shipping_address_name = address_name
		quotation.shipping_address = address_display
		quotation.customer_address = quotation.customer_address or address_name
		address_doc = next((doc for doc in billing_addresses if doc["name"] == address_name), None)

	if billing_address_is_same_as_shipping_address:
		quotation.customer_address = quotation.shipping_address_name = address_name
		quotation.address_display = quotation.shipping_address = address_display

	if not validate_shipping_rule(quotation, throw_exception=False):
		quotation.shipping_rule = None

	apply_cart_settings(quotation=quotation)

	quotation.flags.ignore_permissions = True
	quotation.save()

	if not no_render:
		return render_quotation(get_cart_quotation(quotation))


def guess_territory():
	territory = None
	geoip_country = frappe.session.get("session_country")
	if geoip_country:
		territory = frappe.db.get_value("Territory", geoip_country)

	return territory or get_root_of("Territory")


def decorate_quotation_doc(doc):
	for d in doc.get("items", []):
		item_code = d.item_code
		fields = ["web_item_name", "thumbnail", "website_image", "description", "route"]

		# Variant Item
		if not frappe.db.exists("Website Item", {"item_code": item_code}):
			variant_data = frappe.db.get_values(
				"Item",
				filters={"item_code": item_code},
				fieldname=["variant_of", "item_name", "image"],
				as_dict=True,
			)[0]
			item_code = variant_data.variant_of
			fields = fields[1:]
			d.web_item_name = variant_data.item_name

			if variant_data.image:  # get image from variant or template web item
				d.thumbnail = variant_data.image
				fields = fields[2:]

		d.update(frappe.db.get_value("Website Item", {"item_code": item_code}, fields, as_dict=True))

	return doc


def _get_cart_quotation(party=None):
	"""Return the open Quotation of type "Shopping Cart" or make a new one"""
	if not party:
		party = get_party()

	cart_settings = get_shopping_cart_settings()

	quotation = frappe.get_all(
		"Quotation",
		fields=["name"],
		filters={
			"party_name": party.name,
			"contact_email": frappe.session.user,
			"order_type": "Shopping Cart",
			"company": cart_settings.company,  # E Commerce Settings -> overrides eventually (Venue Settings)
			"docstatus": 0,
		},
		order_by="modified desc",
		limit_page_length=1,
	)

	if quotation:
		qdoc = frappe.get_doc("Quotation", quotation[0].name)
	else:
		company = cart_settings.company
		qdoc = frappe.get_doc(
			{
				"doctype": "Quotation",
				"naming_series": cart_settings.quotation_series or "QTN-CART-",
				"quotation_to": party.doctype,
				"company": company,
				"order_type": "Shopping Cart",
				"status": "Draft",
				"docstatus": 0,
				"__islocal": 1,
				"party_name": party.name,
				"tc_name": frappe.db.get_value("Company", company, "default_selling_terms"),
			}
		)

		qdoc.contact_person = frappe.db.get_value("Contact", {"email_id": frappe.session.user})
		qdoc.contact_email = frappe.session.user

		if qdoc.tc_name:
			qdoc.terms = frappe.db.get_value("Terms and Conditions", qdoc.tc_name, "terms")

		qdoc.flags.ignore_permissions = True
		qdoc.run_method("set_missing_values")
		apply_cart_settings(party, qdoc)

	return qdoc


def update_party(fullname, company_name=None, mobile_no=None, phone=None):
	party = get_party()

	party.customer_name = company_name or fullname
	party.customer_type = "Company" if company_name else "Individual"

	contact_name = frappe.db.get_value("Contact", {"email_id": frappe.session.user})
	contact = frappe.get_doc("Contact", contact_name)
	contact.first_name = fullname
	contact.last_name = None
	contact.customer_name = party.customer_name
	contact.mobile_no = mobile_no
	contact.phone = phone
	contact.flags.ignore_permissions = True
	contact.save()

	party_doc = frappe.get_doc(party.as_dict())
	party_doc.flags.ignore_permissions = True
	party_doc.save()

	qdoc = _get_cart_quotation(party)
	if not qdoc.get("__islocal"):
		qdoc.customer_name = company_name or fullname
		qdoc.run_method("set_missing_lead_customer_details")
		qdoc.flags.ignore_permissions = True
		qdoc.save()


def apply_cart_settings(party=None, quotation=None):
	if not party:
		party = get_party()
	if not quotation:
		quotation = _get_cart_quotation(party)

	cart_settings = get_shopping_cart_settings()

	set_price_list_and_rate(quotation, cart_settings)

	quotation.run_method("calculate_taxes_and_totals")

	set_taxes(quotation, cart_settings)

	_apply_shipping_rule(party, quotation, cart_settings)


def set_price_list_and_rate(quotation, cart_settings):
	"""set price list based on billing territory"""

	_set_price_list(cart_settings, quotation)

	# reset values
	quotation.price_list_currency = (
		quotation.currency
	) = quotation.plc_conversion_rate = quotation.conversion_rate = None
	for item in quotation.get("items"):
		item.price_list_rate = item.discount_percentage = item.rate = item.amount = None

	# refetch values
	quotation.run_method("set_price_list_and_item_details")

	if hasattr(frappe.local, "cookie_manager"):
		# set it in cookies for using in product page
		frappe.local.cookie_manager.set_cookie("selling_price_list", quotation.selling_price_list)


def _set_price_list(cart_settings, quotation=None):
	"""Set price list based on customer or shopping cart default"""
	from erpnext.accounts.party import get_default_price_list

	party_name = quotation.get("party_name") if quotation else get_party().get("name")
	selling_price_list = None

	# check if default customer price list exists
	if party_name and frappe.db.exists("Customer", party_name):
		selling_price_list = get_default_price_list(frappe.get_doc("Customer", party_name))

	# check default price list in shopping cart
	if not selling_price_list:
		selling_price_list = cart_settings.price_list

	if quotation:
		quotation.selling_price_list = selling_price_list

	return selling_price_list


def set_taxes(quotation, cart_settings):
	"""set taxes based on billing territory"""
	from erpnext.accounts.party import set_taxes

	customer_group = frappe.db.get_value("Customer", quotation.party_name, "customer_group")

	quotation.taxes_and_charges = set_taxes(
		quotation.party_name,
		"Customer",
		None,
		quotation.company,
		customer_group=customer_group,
		supplier_group=None,
		tax_category=quotation.tax_category,
		billing_address=quotation.customer_address,
		shipping_address=quotation.shipping_address_name,
		use_for_shopping_cart=1,
		doctype="Quotation",
	)

	# clear table
	quotation.set("taxes", [])

	# append taxes
	quotation.append_taxes_from_master()


def get_party(user=None):
	if not user:
		user = frappe.session.user

	contact_name = get_contact_name(user)
	party = None

	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		if contact.links:
			party_doctype = contact.links[0].link_doctype
			party = contact.links[0].link_name

	cart_settings = get_shopping_cart_settings()

	debtors_account = ""

	if cart_settings.enable_checkout:
		debtors_account = get_debtors_account(cart_settings)

	if party:
		return frappe.get_doc(party_doctype, party)

	else:
		if not cart_settings.enabled:
			frappe.local.flags.redirect_location = "/contact"
			raise frappe.Redirect
		customer = frappe.new_doc("Customer")
		fullname = get_fullname(user)
		customer.update(
			{
				"customer_name": fullname,
				"customer_type": "Individual",
				"customer_group": cart_settings.default_customer_group,
				"territory": get_root_of("Territory"),
			}
		)

		if debtors_account:
			customer.update({"accounts": [{"company": cart_settings.company, "account": debtors_account}]})

		customer.flags.ignore_mandatory = True
		customer.insert(ignore_permissions=True)

		contact = frappe.new_doc("Contact")
		contact.update({"first_name": fullname, "email_ids": [{"email_id": user, "is_primary": 1}]})
		contact.append("links", dict(link_doctype="Customer", link_name=customer.name))
		contact.flags.ignore_mandatory = True
		contact.insert(ignore_permissions=True)

		return customer


def get_debtors_account(cart_settings):
	if not cart_settings.no_payment_gateway and not cart_settings.payment_gateway_account:
		frappe.throw(_("Payment Gateway Account not set"), _("Mandatory"))

	payment_gateway_account_currency = (
		frappe.db.get_value("Price List", cart_settings.price_list, "currency")
		if cart_settings.no_payment_gateway
		else frappe.db.get_value(
			"Payment Gateway Account", cart_settings.payment_gateway_account, "currency"
		)
	)

	account_name = _("Debtors ({0})").format(payment_gateway_account_currency)

	debtors_account_name = get_account_name(
		account_type="Receivable",
		root_type="Asset",
		is_group=0,
		account_currency=payment_gateway_account_currency,
		company=cart_settings.company,
	)

	if not debtors_account_name:
		# For a given currency and company, if no account was found,
		# then try to create it.

		parent_account = get_account_name(
			root_type="Asset",
			is_group=1,
			account_currency=payment_gateway_account_currency,
			company=cart_settings.company,
		)

		if not parent_account:
			frappe.throw(
				frappe._("Missing group for debtors account for company '{0}' and currency '{1}'").format(
					cart_settings.company, payment_gateway_account_currency
				)
			)

		debtors_account = frappe.get_doc(
			{
				"doctype": "Account",
				"account_type": "Receivable",
				"root_type": "Asset",
				"is_group": 0,
				"parent_account": parent_account,
				"account_name": account_name,
				"currency": payment_gateway_account_currency,
				"company": cart_settings.company,
			}
		).insert(ignore_permissions=True)

		return debtors_account.name

	else:
		return debtors_account_name


def get_address_docs(
	doctype=None, txt=None, filters=None, limit_start=0, limit_page_length=20, party=None
):
	if not party:
		party = get_party()

	if not party:
		return []

	address_names = frappe.db.get_all(
		"Dynamic Link",
		fields=("parent"),
		filters=dict(parenttype="Address", link_doctype=party.doctype, link_name=party.name),
	)

	out = []

	for a in address_names:
		address = frappe.get_doc("Address", a.parent)
		address.display = get_address_display(address.as_dict())
		out.append(address)

	return out


@frappe.whitelist()
def apply_shipping_rule(shipping_rule):
	quotation = _get_cart_quotation()

	quotation.shipping_rule = shipping_rule
	ensure_addresses_are_valid(quotation)
	apply_cart_settings(quotation=quotation)

	quotation.flags.ignore_permissions = True
	quotation.save()

	return render_quotation(get_cart_quotation(quotation))


def _apply_shipping_rule(party=None, quotation=None, cart_settings=None):
	if quotation.shipping_rule:
		quotation.run_method("apply_shipping_rule")
		quotation.run_method("calculate_taxes_and_totals")


def ensure_addresses_are_valid(quotation):
	"""Ensure that addresses are in the list of addresses for the customer"""
	shipping_addresses = [x["name"] for x in get_shipping_addresses()]
	if (
		shipping_addresses
		and quotation.shipping_address_name
		and quotation.shipping_address_name not in shipping_addresses
	):
		quotation.shipping_address_name = shipping_addresses[0]
	billing_addresses = [x["name"] for x in get_billing_addresses()]
	if (
		billing_addresses
		and quotation.customer_address
		and quotation.customer_address not in billing_addresses
	):
		quotation.customer_address = billing_addresses[0]


def get_shipping_rules(quotation=None):
	if not quotation:
		quotation = _get_cart_quotation()

	from erpnext.accounts.doctype.shipping_rule.shipping_rule import get_ecommerce_shipping_rules

	return get_ecommerce_shipping_rules(quotation)


def get_address_territory(address_name):
	"""Tries to match city, state and country of address to existing territory"""
	territory = None

	if address_name:
		address_fields = frappe.db.get_value("Address", address_name, ["city", "state", "country"])
		for value in address_fields:
			territory = frappe.db.get_value("Territory", value)
			if territory:
				break

	return territory


def show_terms(doc):
	return doc.tc_name


@frappe.whitelist(allow_guest=True)
def apply_coupon_code(applied_code, applied_referral_sales_partner):
	quotation = True

	if not applied_code:
		frappe.throw(_("Please enter a coupon code"))

	coupon_list = frappe.get_all("Coupon Code", filters={"coupon_code": applied_code})
	if not coupon_list:
		frappe.throw(_("Please enter a valid coupon code"))

	coupon_name = coupon_list[0].name

	from erpnext.accounts.doctype.pricing_rule.utils import validate_coupon_code

	validate_coupon_code(coupon_name)
	quotation = _get_cart_quotation()
	quotation.coupon_code = coupon_name
	quotation.flags.ignore_permissions = True
	quotation.save()

	if applied_referral_sales_partner:
		sales_partner_list = frappe.get_all(
			"Sales Partner", filters={"referral_code": applied_referral_sales_partner}
		)
		if sales_partner_list:
			sales_partner_name = sales_partner_list[0].name
			quotation.referral_sales_partner = sales_partner_name
			quotation.flags.ignore_permissions = True
			quotation.save()

	return quotation


def get_estimates_for_shipping(quotation, shipping_rules: list[str]):
	"""Returns shipping estimates for given shipping rules"""

	from frappe.utils.data import fmt_money

	estimates = {}

	for shipping_rule in shipping_rules:
		shipping_amount = shipping_rule.get_shipping_amount(quotation)

		if shipping_amount == "not applicable":
			shipping_amount = "not applicable"
		elif shipping_amount == 0:
			shipping_amount = _("Free")
		elif isinstance(shipping_amount, (int, float)):
			shipping_amount = fmt_money(flt(shipping_amount), currency=quotation.currency)
		else:
			shipping_amount = None

		estimates[shipping_rule.name] = shipping_amount

	return estimates


def validate_shipping_rule(quotation, cart_settings=None, throw_exception=True) -> bool:
	shipping_rules = get_shipping_rules(quotation)

	if shipping_rules or quotation.shipping_rule:
		if not quotation.shipping_rule:
			if throw_exception:
				frappe.throw(_("Please select a shipping method"))
			return False

		shipping_rules_names = {shipping_rule.name for shipping_rule in shipping_rules}
		if not shipping_rules or quotation.shipping_rule not in shipping_rules_names:
			if throw_exception:
				apply_shipping_rule(None)
				frappe.db.commit()
				frappe.throw(_("The shipping method is no longer applicable"))
			return False

	return True


@frappe.whitelist()
def rerender_cart():
	return render_quotation()


@frappe.whitelist()
def get_custom_address_fields(cart_settings):
	"""Returns custom fields for the address form"""

	if not cart_settings.custom_address_form:
		return []

	fields = []
	for field in cart_settings.custom_address_form:
		if field.fieldtype == "Link":
			field.fieldtype = "Autocomplete"
			title_field = frappe.db.get_value("DocType", "Country", "title_field", cache=True)
			search = ["name as value", f"{title_field} as label"] if title_field else ["name as value"]
			field.options = []
			for d in frappe.get_list("Country", fields=search):
				if title_field:
					field.options.append({"value": d.value, "label": d.label})
				else:
					field.options.append(d.value)

			field.options = frappe.as_json(field.options)

		fields.append(field)

	return fields
