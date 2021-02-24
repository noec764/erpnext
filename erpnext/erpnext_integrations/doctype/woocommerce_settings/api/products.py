import frappe
from frappe.utils import flt, now_datetime, get_datetime
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI
from erpnext.utilities.product import get_price, get_qty_in_stock
from frappe.utils.nestedset import get_root_of

PER_PAGE = 100

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
	response = wc_api.get_products()
	products = response.json()

	for page_idx in range(1, int(response.headers.get('X-WP-TotalPages')) or 1):
		response = wc_api.get_products(params={
			"per_page": PER_PAGE,
			"page": page_idx + 1
		})
	products.extend(response.json())

	for product in frappe.parse_json(products):
		try:
			create_item(wc_api, product)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "WooCommerce Products Sync Error")

def sync_products():
	wc_api = WooCommerceProducts()
	for item in get_items():
		woo_item = prepare_item(wc_api.settings, item)

		try:
			res = wc_api.create_or_update(woo_item)
			if not item.get("woocommerce_id"):
				frappe.db.set_value("Item", item.name, "woocommerce_id", res.get("id"))
			frappe.db.set_value("Item", item.name, "last_woocommerce_sync", now_datetime())

		except Exception as e:
			frappe.log_error(e, "Woocommerce Sync Error")

def get_items():
	woocommerce_items = frappe.get_all("Item",
		filters={"sync_with_woocommerce": 1, "disabled": 0, "variant_of": ("is", "not set")},
		fields=[
			"name", "modified", "last_woocommerce_sync", "has_variants", "web_long_description",
			"description", "website_content", "item_code", "stock_uom", "weight_per_unit", "weight_uom",
			"is_stock_item", "variant_of", "website_warehouse", "woocommerce_id", "item_name"
		]
	)

	items_to_sync = [x for x in woocommerce_items if get_datetime(x.modified) > get_datetime(x.last_woocommerce_sync)]

	excluded_items = [x for x in woocommerce_items if get_datetime(x.modified) <= get_datetime(x.last_woocommerce_sync)]

	for item in excluded_items:
		if frappe.get_all("Item Price", filters={"modified": (">", item.last_woocommerce_sync)}, limit=1):
			items_to_sync.append(item)

	return items_to_sync

def prepare_item(settings, item):
	item_data = {
		"name": item.item_name,
		"sku": item.item_code,
		"description": item.get("web_long_description") or item.get("description"),
		"short_description": item.get("website_content") or item.get("description"),
		"manage_stock": f"{True if item.is_stock_item else False}"
	}

	if item.get("woocommerce_id"):
		item_data["id"] = item.get("woocommerce_id")

	price = get_price(item.item_code, settings.price_list, settings.customer_group, settings.company, qty=1)
	item_data.update({
		"regular_price": f"{flt(price.get('price_list_rate'))}"
	})

	if item.weight_per_unit and item.weight_uom and item.weight_uom.lower() in ["kg", "g", "oz", "lb", "lbs"]:
		item_data.update({
			"weight": f"{get_weight_in_woocommerce_unit(settings.weight_unit, item.weight_per_unit, item.weight_uom)}"
		})

	if item.is_stock_item:
		qty_in_stock = get_qty_in_stock(item.item_code, "website_warehouse", settings.warehouse)
		if qty_in_stock.stock_qty:
			item_data.update({
				"stock_quantity": f"{qty_in_stock.stock_qty[0][0]}"
			})

	if item.has_variants:
		item_data.update({
			"type": "variable"
		})

		if item.variant_of:
			item = frappe.get_doc("Item", item.variant_of)

		variant_list, options, variant_item_name = get_variant_attributes(item, settings.price_list, item.website_warehouse)
		item_data["attributes"] = options

	else:
		item_data["type"] = "simple"

	return item_data

def get_weight_in_woocommerce_unit(weight_unit, weight, weight_uom):
	convert_to_gram = {
		"kg": 1000,
		"lb": 453.592,
		"lbs": 453.592,
		"oz": 28.3495,
		"g": 1
	}
	convert_to_oz = {
		"kg": 0.028,
		"lb": 0.062,
		"lbs": 0.062,
		"oz": 1,
		"g": 28.349
	}
	convert_to_lb = {
		"kg": 1000,
		"lb": 1,
		"lbs": 1,
		"oz": 16,
		"g": 0.453
	}
	convert_to_kg = {
		"kg": 1,
		"lb": 2.205,
		"lbs": 2.205,
		"oz": 35.274,
		"g": 1000
	}
	if weight_unit.lower() == "g":
		return weight * convert_to_gram[weight_uom.lower()]

	if weight_unit.lower() == "oz":
		return weight * convert_to_oz[weight_uom.lower()]

	if weight_unit.lower() == "lb"  or weight_unit.lower() == "lbs":
		return weight * convert_to_lb[weight_uom.lower()]

	if weight_unit.lower() == "kg":
		return weight * convert_to_kg[weight_uom.lower()]

def get_variant_attributes(item, price_list, warehouse):
	options, variant_list, variant_item_name, attr_sequence = [], [], [], []
	attr_dict = {}

	for i, variant in enumerate(frappe.get_all("Item", filters={"variant_of": item.get("name")},
		fields=['name'])):

		item_variant = frappe.get_doc("Item", variant.get("name"))

		data = (get_price_and_stock_details(item_variant, warehouse, price_list))
		data["item_name"] = item_variant.name
		data["attributes"] = []
		for attr in item_variant.get('attributes'):
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
		options.append({
			"name": attr,
			"visible": "True",
			"variation": "True",
			"position": i+1,
			"options": list(set(attr_dict[attr]))
		})
	return variant_list, options, variant_item_name


def create_item(wc_api, product):
	attributes = create_attributes(product)
	if product.get("variations"):
		create_template(wc_api, product, attributes)
	elif not frappe.db.exists("Item", {"woocommerce_id": product.get("id")}):
		create_simple_item(wc_api.settings, product)

	frappe.db.commit()

def create_template(wc_api, product, attributes):
	if not frappe.db.exists("Item", {"woocommerce_id": product.get("id")}):
		template_dict = get_simple_item(wc_api.settings, product)
		template_dict.update({
			"has_variants": True,
			"attributes": attributes
		})

		try:
			template = frappe.get_doc(template_dict).insert(ignore_permissions=True)
		except frappe.exceptions.DuplicateEntryError:
			template = frappe.get_doc("Item", dict(item_code=template_dict.get("item_code")))

	else:
		template = frappe.get_doc("Item", dict(woocommerce_id=product.get("id")))

	for variant in product.get("variations"):
		create_variant(wc_api, variant, template, attributes)

def create_variant(wc_api, variant, template, attributes):
	product = wc_api.get(f"products/{variant}").json()
	item = get_simple_item(wc_api.settings, product)
	item.update({
		"item_code": product.get("slug") or product.get("sku"),
		"variant_of": template.name,
		"attributes": [
			{
				"attribute": x.get("name"),
				"attribute_value": x.get("option")[:140]
			} for x in product.get("attributes")
		]
	})
	try:
		frappe.get_doc(item).insert(ignore_permissions=True)
	except frappe.exceptions.DuplicateEntryError as e:
		pass

def create_simple_item(settings, product):
	item = get_simple_item(settings, product)
	try:
		frappe.get_doc(item).insert(ignore_permissions=True)
	except frappe.exceptions.DuplicateEntryError as e:
		pass

def get_simple_item(settings, product):
	return {
		"doctype": "Item",
		"woocommerce_id": product.get("id"),
		"sync_with_woocommerce": 1,
		"is_stock_item": product.get("manage_stock"),
		"item_code": product.get("sku") or product.get("slug"),
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
	}

def get_item_group(categories):
	for category in categories:
		if frappe.db.exists("Item Group", category.get("name")):
			return category.name
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
	for attr in product.get('attributes'):
		if not frappe.db.get_value("Item Attribute", attr.get("name"), "name"):
			new_item_attribute_entry = frappe.get_doc({
				"doctype": "Item Attribute",
				"attribute_name": attr.get("name"),
				"woocommerce_id": attr.get("id"),
				"item_attribute_values": []
			})
			
			for attr_value in attr.get("options"):
				row = new_item_attribute_entry.append('item_attribute_values', {})
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
		if not any((d.abbr.lower() == attr_value[:140].lower() or d.attribute_value.lower() == attr_value[:140].lower())\
		for d in item_attr.item_attribute_values):
			item_attr.append("item_attribute_values", {
				"attribute_value": attr_value[:140],
				"abbr": attr_value[:140]
			})
	return item_attr

def update_stock(doc, method):
	print("UPDATE STOCK", doc.as_dict())
	wc_api = WooCommerceProducts()