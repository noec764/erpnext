import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime
from frappe.utils.nestedset import get_root_of
from requests.exceptions import HTTPError

from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI
from erpnext.utilities.product import get_price


class WooCommerceProducts(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceProducts, self).__init__(version, args, kwargs)

	def create_or_update(self, data):
		if not data.get("id"):
			return self.post("products", data).json()
		else:
			return self.put(f"products/{data.get('id')}", data).json()

	def get_products(self, params=None):
		return self.get("products", params=params)


def sync_items():
	wc_api = WooCommerceProducts()
	response = wc_api.get_products(params={"status": "publish"})
	products = response.json()

	for page_idx in range(1, int(response.headers.get("X-WP-TotalPages")) + 1):
		response = wc_api.get_products(params={"per_page": 100, "page": page_idx, "status": "publish"})
		products.extend(response.json())

	products_list = frappe.parse_json(products)
	for product in sorted(products_list, key=lambda x: (x.get("type") != "woobs", x.get("type"))):
		try:
			create_item(wc_api, product)
		except Exception:
			frappe.log_error(
				message=_("Product: {0}\n\n{1}").format(product.get("id"), frappe.get_traceback()),
				title=_("WooCommerce Products Sync Error"),
			)


def sync_products():
	wc_api = WooCommerceProducts()

	for item in get_items():
		woo_item = prepare_item(wc_api.settings, item)

		try:
			res = wc_api.create_or_update(woo_item)
			if not item.get("woocommerce_id"):
				frappe.db.set_value("Item", item.name, "woocommerce_id", res.get("id"))
			frappe.db.set_value("Item", item.name, "last_woocommerce_sync", now_datetime())

		except Exception:
			frappe.log_error(_("Woocommerce Sync Error"))


def get_items():
	woocommerce_items = frappe.get_all(
		"Item",
		filters={"sync_with_woocommerce": 1, "disabled": 0, "variant_of": ("is", "not set")},
		fields=[
			"name",
			"modified",
			"last_woocommerce_sync",
			"has_variants",
			"web_long_description",
			"description",
			"website_content",
			"item_code",
			"stock_uom",
			"weight_per_unit",
			"weight_uom",
			"is_stock_item",
			"variant_of",
			"website_warehouse",
			"woocommerce_id",
			"item_name",
		],
	)

	items_to_sync = [
		x for x in woocommerce_items if get_datetime(x.modified) > get_datetime(x.last_woocommerce_sync)
	]

	excluded_items = [
		x for x in woocommerce_items if get_datetime(x.modified) <= get_datetime(x.last_woocommerce_sync)
	]

	for item in excluded_items:
		if frappe.get_all(
			"Item Price", filters={"modified": (">", item.last_woocommerce_sync)}, limit=1
		):
			items_to_sync.append(item)

	return items_to_sync


def prepare_item(settings, item):
	item_data = {
		"name": item.item_name,
		"sku": item.item_code,
		"description": item.get("web_long_description") or item.get("description"),
		"short_description": item.get("website_content") or item.get("description"),
		"manage_stock": f"{True if item.is_stock_item else False}",
	}

	if item.get("woocommerce_id"):
		item_data["id"] = item.get("woocommerce_id")

	item_data.update(get_price_and_qty(item, settings))

	if item.has_variants:
		item_data.update({"type": "variable"})

		if item.variant_of:
			item = frappe.get_doc("Item", item.variant_of)

		variant_list, options, variant_item_name = get_variant_attributes(item, settings)
		item_data["attributes"] = options

	else:
		item_data["type"] = "simple"

	return item_data


def get_price_and_qty(item, settings):
	price = get_price(
		item.item_code, settings.price_list, settings.customer_group, settings.company, qty=1
	)
	item_data = {"regular_price": f"{flt(price.get('price_list_rate') if price else 0.0)}"}

	if (
		item.weight_per_unit
		and item.weight_uom
		and item.weight_uom.lower() in ["kg", "g", "oz", "lb", "lbs"]
	):
		item_data.update(
			{
				"weight": f"{get_weight_in_woocommerce_unit(settings.weight_unit, item.weight_per_unit, item.weight_uom)}"
			}
		)

	if item.is_stock_item:
		qty_in_stock = (item.item_code, "website_warehouse", settings.warehouse)
		if qty_in_stock.stock_qty:
			item_data.update({"stock_quantity": f"{qty_in_stock.stock_qty[0][0]}"})

	return item_data


def get_weight_in_woocommerce_unit(weight_unit, weight, weight_uom):
	convert_to_gram = {"kg": 1000, "lb": 453.592, "lbs": 453.592, "oz": 28.3495, "g": 1}
	convert_to_oz = {"kg": 0.028, "lb": 0.062, "lbs": 0.062, "oz": 1, "g": 28.349}
	convert_to_lb = {"kg": 1000, "lb": 1, "lbs": 1, "oz": 16, "g": 0.453}
	convert_to_kg = {"kg": 1, "lb": 2.205, "lbs": 2.205, "oz": 35.274, "g": 1000}
	if weight_unit.lower() == "g":
		return weight * convert_to_gram[weight_uom.lower()]

	if weight_unit.lower() == "oz":
		return weight * convert_to_oz[weight_uom.lower()]

	if weight_unit.lower() == "lb" or weight_unit.lower() == "lbs":
		return weight * convert_to_lb[weight_uom.lower()]

	if weight_unit.lower() == "kg":
		return weight * convert_to_kg[weight_uom.lower()]


def get_variant_attributes(item, settings):
	options, variant_list, variant_item_name, attr_sequence = [], [], [], []
	attr_dict = {}

	for i, variant in enumerate(
		frappe.get_all("Item", filters={"variant_of": item.get("name")}, fields=["name"])
	):

		item_variant = frappe.get_doc("Item", variant.get("name"))

		data = get_price_and_qty(item_variant, settings)
		data["item_name"] = item_variant.name
		data["attributes"] = []
		for attr in item_variant.get("attributes"):
			attribute_option = {}
			attribute_option["name"] = attr.attribute
			attribute_option["option"] = attr.attribute_value
			data["attributes"].append(attribute_option)

			if attr.attribute not in attr_sequence:
				attr_sequence.append(attr.attribute)
			if not attr_dict.get(attr.attribute):
				attr_dict.setdefault(attr.attribute, [])

			attr_dict[attr.attribute].append(attr.attribute_value)

		variant_list.append(data)

	for i, attr in enumerate(attr_sequence):
		options.append(
			{
				"name": attr,
				"visible": "True",
				"variation": "True",
				"position": i + 1,
				"options": list(set(attr_dict[attr])),
			}
		)
	return variant_list, options, variant_item_name


def create_item(wc_api, product):
	attributes = create_attributes(product)
	if product.get("variations"):
		create_template(wc_api, product, attributes)
	elif not frappe.db.exists("Item", {"woocommerce_id": product.get("id")}):
		create_simple_item(wc_api.settings, product)

	frappe.db.commit()

	if product.get("type") in ("woosb"):
		create_product_bundle(wc_api.settings, product)

	frappe.db.commit()


def create_template(wc_api, product, attributes):
	if not frappe.db.exists("Item", {"woocommerce_id": product.get("id")}):
		template_dict = get_simple_item(wc_api.settings, product)
		template_dict.update({"has_variants": True, "attributes": attributes})

		try:
			template = frappe.get_doc(template_dict).insert(ignore_permissions=True)
		except frappe.exceptions.DuplicateEntryError:
			template = frappe.get_doc("Item", dict(item_code=template_dict.get("item_code")))

	else:
		template = frappe.get_doc("Item", dict(woocommerce_id=product.get("id")))

	for variant in product.get("variations"):
		create_variant(wc_api, variant, template, attributes)


def create_variant(wc_api, variant, template, attributes):
	if not frappe.db.exists("Item", dict(woocommerce_id=variant)):
		product = wc_api.get(f"products/{variant}").json()
		item = get_simple_item(wc_api.settings, product)

		item.update(
			{
				"item_code": get_item_code(product),
				"variant_of": template.name,
				"attributes": [
					{"attribute": x.get("name"), "attribute_value": x.get("option")[:140]}
					for x in product.get("attributes")
				],
			}
		)
		try:
			frappe.get_doc(item).insert(ignore_permissions=True)
		except frappe.exceptions.DuplicateEntryError:
			pass
		except Exception:
			print(product.get("slug") or product.get("sku"), product.get("id"), frappe.get_traceback())


def create_simple_item(settings, product):
	item = get_simple_item(settings, product)
	try:
		frappe.get_doc(item).insert(ignore_permissions=True)
	except frappe.exceptions.DuplicateEntryError:
		pass


def create_product_bundle(settings, product):
	"""
	Specific integration for WPC Product Bundles for WooCommerce
	Can be extended for other product bundle plugins
	"""
	bundle_item = frappe.db.get_value("Item", dict(woocommerce_id=product.get("id")))
	if bundle_item and not frappe.db.exists("Product Bundle", bundle_item):
		items = []
		for meta in product.get("meta_data"):
			if meta.get("key") == "woosb_ids":
				for d in meta.get("value").split(","):
					code, qty = d.split("/")
					item_code = frappe.db.get_value("Item", dict(woocommerce_id=code))
					if item_code:
						items.append({"item_code": item_code, "qty": cint(qty)})

		if items:
			frappe.get_doc(
				{
					"doctype": "Product Bundle",
					"new_item_code": bundle_item,
					"description": product.get("name"),
					"items": items,
				}
			).insert(ignore_permissions=True)


def get_simple_item(settings, product):
	return {
		"doctype": "Item",
		"woocommerce_id": product.get("id"),
		"sync_with_woocommerce": 1,
		"is_stock_item": product.get("manage_stock"),
		"item_code": get_item_code(product),
		"item_name": product.get("name"),
		"description": product.get("description") or product.get("name"),
		"item_group": get_item_group(product.get("categories")),
		"has_variants": False,
		"stock_uom": settings.default_uom,
		"default_warehouse": settings.warehouse,
		"image": get_item_image(product),
		"weight_uom": product.get("weight_unit"),
		"weight_per_unit": product.get("weight"),
		"web_long_description": product.get("short_description") or product.get("name"),
		"include_item_in_manufacturing": 0,
		"standard_rate": product.get("price"),
		"item_defaults": [
			{
				"company": settings.company,
				"default_warehouse": settings.warehouse,
				"default_price_list": settings.price_list,
			}
		],
	}


def get_item_code(product):
	item_code = product.get("sku")

	if not item_code or frappe.db.exists("Item", item_code):
		item_code = product.get("slug")

	if frappe.db.exists("Item", item_code):
		item_code = product.get("name")

		if frappe.db.exists("Item", item_code):
			item_code = product.get("id")

	return str(item_code)


def get_item_group(categories):
	for category in categories:
		if frappe.db.exists("Item Group", category.get("name")):
			return category.get("name")
	else:
		if categories:
			item_category = frappe.get_doc(
				{
					"doctype": "Item Group",
					"parent_item_group": get_root_of("Item Group"),
					"item_group_name": categories[0].get("name"),
				}
			).insert(ignore_permissions=True)
			return item_category.name
		else:
			return get_root_of("Item Group")


def get_item_image(product):
	if product.get("images"):
		if len(product.get("images")) == 1:
			return product.get("images")[0].get("src")
		for image in product.get("images"):
			if image.get("position") == 0:
				return image.get("src")


def create_attributes(product):
	attributes = []
	for attr in product.get("attributes"):
		if not frappe.db.get_value("Item Attribute", attr.get("name"), "name"):
			new_item_attribute_entry = frappe.get_doc(
				{
					"doctype": "Item Attribute",
					"attribute_name": attr.get("name"),
					"woocommerce_id": attr.get("id"),
					"item_attribute_values": [],
				}
			)

			for attr_value in attr.get("options"):
				row = new_item_attribute_entry.append("item_attribute_values", {})
				row.attribute_value = attr_value[:140]
				row.abbr = attr_value[:140]

			new_item_attribute_entry.insert(ignore_permissions=True)
		else:
			item_attr = frappe.get_doc("Item Attribute", attr.get("name"))
			if not item_attr.numeric_values:
				item_attr.woocommerce_id = attr.get("id")
				old_len = len(item_attr.item_attribute_values)
				item_attr = set_new_attribute_values(item_attr, attr.get("options"))
				if len(item_attr.item_attribute_values) > old_len:
					item_attr.save()
		attributes.append({"attribute": attr.get("name")})

	return attributes


def set_new_attribute_values(item_attr, values):
	for attr_value in values:
		if not any(
			(
				d.abbr.lower() == attr_value[:140].lower()
				or d.attribute_value.lower() == attr_value[:140].lower()
			)
			for d in item_attr.item_attribute_values
		):
			item_attr.append(
				"item_attribute_values", {"attribute_value": attr_value[:140], "abbr": attr_value[:140]}
			)
	return item_attr


def update_stock(doc, method):
	frappe.enqueue(
		"erpnext.erpnext_integrations.doctype.woocommerce_settings.api.products._update_stock", doc=doc
	)


def _update_stock(doc):
	try:
		wc_api = WooCommerceProducts()
		if not wc_api.api:
			return

		item = frappe.get_cached_doc("Item", doc.item_code)

		if item.get("woocommerce_id") and item.get("sync_with_woocommerce"):
			if item.get("website_warehouse") == doc.warehouse or (
				not item.get("website_warehouse") and wc_api.settings.warehouse == doc.warehouse
			):

				product = wc_api.get(f"products/{item.get('woocommerce_id')}").json()

				if product.get("stock_quantity") != doc.actual_qty:
					wc_api.put(f"products/{item.get('woocommerce_id')}", {"stock_quantity": doc.actual_qty})

	except HTTPError as http_err:
		# If item is a variant, it will not be found
		if http_err.response.status_code != 404:
			frappe.log_error(_("Woocommerce stock update error"))

	except Exception:
		frappe.log_error(_("Woocommerce stock update error"))
