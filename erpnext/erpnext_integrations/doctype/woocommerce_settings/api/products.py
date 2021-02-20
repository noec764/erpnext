import frappe
from frappe.utils import flt, now_datetime, get_datetime
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI
from erpnext.utilities.product import get_price, get_qty_in_stock

class WooCommerceProducts(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceProducts, self).__init__(version, args, kwargs)

	def create_or_update(self, data):
		if not data.get("id"):
			return self.post("products", data).json()
		else:
			return self.put(f"products/{data.get('id')}", data).json()

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