from collections import defaultdict
import frappe
from frappe.contacts.doctype.address.address import get_preferred_address
from frappe.utils import nowdate, cint, flt, now_datetime
from frappe import _

from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.customers import sync_customer

PER_PAGE = 100

class WooCommerceOrders(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceOrders, self).__init__(version, args, kwargs)

	def get_orders(self, params=None):
		return self.get("orders", params=params)

class WooCommerceTaxes(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceTaxes, self).__init__(version, args, kwargs)

	def get_tax(self, id, params=None):
		return self.get(f"taxes/{id}", params=params).json()

	def get_taxes(self, params=None):
		return self.get(f"taxes", params=params).json()

class WooCommerceShippingMethods(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceShippingMethods, self).__init__(version, args, kwargs)

	def get_shipping_methods(self, params=None):
		return self.get(f"shipping_methods", params=params).json()

def sync_orders():
	wc_api = WooCommerceOrders()

	woocommerce_orders = get_woocommerce_orders(wc_api)

	for woocommerce_order in woocommerce_orders:
		frappe.enqueue(sync_order, queue='long', wc_api=wc_api, woocommerce_order=woocommerce_order)

def sync_order(wc_api, woocommerce_order):
	customer = _sync_customer(wc_api, woocommerce_order.get("customer_id"))
	if customer:
		if frappe.db.exists("Sales Order", dict(woocommerce_id=woocommerce_order.get("id"), docstatus=1)):
			_update_sales_order(wc_api.settings, woocommerce_order, customer)
		else:
			_new_sales_order(wc_api.settings, woocommerce_order, customer)

def _sync_customer(wc_api, id):
	try:
		woocommerce_customer = wc_api.get(f"customers/{id}").json()
		return sync_customer(wc_api.settings, woocommerce_customer)
	except Exception as e:
		frappe.log_error(str(e), "Woocommerce Customer Error")

def get_woocommerce_orders(wc_api):
	response = wc_api.get_orders()
	woocommerce_orders = response.json()

	for page_idx in range(1, int(response.headers.get('X-WP-TotalPages')) or 1):
		response = wc_api.get_orders(params={
			"per_page": PER_PAGE,
			"page": page_idx + 1
		})
		woocommerce_orders.extend(response.json())

	return woocommerce_orders

def create_sales_order(settings, woocommerce_order, customer):
	return frappe.get_doc({
		"doctype": "Sales Order",
		"order_type": "Shopping Cart",
		"naming_series": settings.sales_order_series,
		"woocommerce_id": woocommerce_order.get("id"),
		"customer": customer.name,
		"customer_group": customer.customer_group,
		"delivery_date": woocommerce_order.get("date_created_gmt") or nowdate(),
		"company": settings.company,
		"selling_price_list": settings.price_list,
		"ignore_pricing_rule": 1,
		"items": get_order_items(woocommerce_order.get("line_items"), settings, woocommerce_order.get("date_created_gmt")),
		"taxes": get_order_taxes(woocommerce_order, settings),
		"currency": woocommerce_order.get("currency"),
		"taxes_and_charges": None,
		"customer_address": get_preferred_address("Customer", customer.name, "is_primary_address"),
		"shipping_address_name": get_preferred_address("Customer", customer.name, "is_shipping_address"),
		"last_woocommerce_sync": now_datetime()
	})

def _new_sales_order(settings, woocommerce_order, customer):
	so = create_sales_order(settings, woocommerce_order, customer)

	if so.items:
		so.flags.ignore_permissions = True
		so.insert()
		so.submit()
	else:
		frappe.log_error(f"No items found for Woocommerce order {woocommerce_order.get('id')}", "Woocommerce Order Error")

def get_order_items(order_items, settings, delivery_date):
	items = []
	for item in order_items:
		item_code = get_item_code_and_warehouse(item)
		if item_code:
			warehouse = frappe.db.get_value("Item", item_code, "website_warehouse")
			stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
			items.append({
				"item_code": item_code,
				"rate": item.get("price"),
				"delivery_date": delivery_date or nowdate(),
				"qty": item.get("quantity"),
				"warehouse": warehouse or settings.warehouse,
				"stock_uom": stock_uom,
				"uom": frappe.db.get_value("Item", item_code, "sales_uom") or stock_uom
			})
		else:
			frappe.log_error(f"Item missing for Woocommerce product: {item.get('product_id')}", "Woocommerce Order Error")

	return items

def get_item_code_and_warehouse(item):
	if cint(item.get("variation_id")) > 0:
		item_code = frappe.db.get_value("Item", {"woocommerce_id": item.get("variation_id")}, "item_code")
	else:
		item_code = frappe.db.get_value("Item", {"woocommerce_id": item.get("product_id")}, "item_code")

	return item_code

def get_order_taxes(order, settings):
	taxes = []
	for tax in order.get("tax_lines"):
		rate = tax.get("rate_percent")
		name = tax.get("label")

		account_head = get_tax_account_head(tax.get("rate_id"))

		if account_head:
			taxes.append({
				"charge_type": "On Net Total" if order.get("prices_include_tax") else "Actual",
				"account_head": account_head,
				"description": name,
				"rate": rate,
				"tax_amount": flt(tax.get("tax_total") or 0) + flt(tax.get("shipping_tax_total") or 0), 
				"included_in_print_rate": 1 if order.get("prices_include_tax") else 0,
				"cost_center": settings.cost_center
			})
		else:
			frappe.log_error(f"Account head missing for Woocommerce tax: {name} @ {rate} %", "Woocommerce Order Error")

	taxes = update_taxes_with_fee_lines(taxes, order.get("fee_lines"), settings)
	taxes = update_taxes_with_shipping_lines(taxes, order.get("shipping_lines"), settings)

	return taxes

def update_taxes_with_fee_lines(taxes, fee_lines, settings):
	for fee_charge in fee_lines:
		taxes.append({
			"charge_type": "Actual",
			"account_head": settings.fee_account,
			"description": fee_charge["name"],
			"tax_amount": fee_charge["amount"],
			"cost_center": settings.cost_center
		})

	return taxes

def update_taxes_with_shipping_lines(taxes, shipping_lines, settings):
	for shipping_charge in shipping_lines:
		account_head = get_shipping_account_head(shipping_charge.get("method_id"))

		if account_head:
			taxes.append({
				"charge_type": "Actual",
				"account_head": account_head,
				"description": shipping_charge.get("method_title"),
				"tax_amount": shipping_charge.get("total"),
				"cost_center": settings.cost_center
			})
		else:
			frappe.log_error(f"Account head missing for Woocommerce shipping method: {shipping_charge.get('method_id')}", "Woocommerce Order Error")

	return taxes

def get_tax_account_head(id):
	accounts = frappe.get_all("Woocommerce Taxes", filters=dict(woocommerce_tax_id=id), fields=["account"], limit=1)
	if accounts:
		return accounts[0].account

def get_shipping_account_head(id):
	accounts = frappe.get_all("Woocommerce Shipping Methods", filters=dict(woocommerce_shipping_method_id=id), fields=["account"], limit=1)
	if accounts:
		return accounts[0].account

def _update_sales_order(settings, woocommerce_order, customer):
	original_so = frappe.get_doc("Sales Order", dict(woocommerce_id=woocommerce_order.get("id"), docstatus=1))
	updated_so = create_sales_order(settings, woocommerce_order, customer)
	sales_order = original_so

	so_are_similar = compare_sales_orders(original_so, updated_so)

	if not so_are_similar and updated_so.items:
		original_so.flags.ignore_permissions = True
		original_so.cancel()

		sales_order = updated_so
		sales_order.flags.ignore_permissions = True
		sales_order.insert()
		sales_order.submit()
		frappe.db.commit()

	if sales_order and woocommerce_order.get("date_paid"):
		register_payment_and_invoice(settings, woocommerce_order, sales_order)

	frappe.db.set_value("Sales Order", sales_order.name, "last_woocommerce_sync", now_datetime())

def compare_sales_orders(original, updated):
	if updated.grand_total and original.grand_total != updated.grand_total:
		return False

	if len(updated.items) and len(original.items) != len(updated.items):
		return False

	if len(original.taxes) and len(updated.taxes) and len(original.taxes) != len(updated.taxes):
		return False

	original_qty_per_item = get_qty_per_item(original.items)
	updated_qty_per_item = get_qty_per_item(updated.items)
	for it in updated_qty_per_item:
		if not original_qty_per_item.get(it):
			return False

		if original_qty_per_item.get(it) != updated_qty_per_item[it]:
			return False

	return True

def get_qty_per_item(items):
	qty_per_item = defaultdict(float)
	for item in items:
		qty_per_item[item.item_code] += item.qty

	return qty_per_item

def register_payment_and_invoice(settings, woocommerce_order, sales_order):
	if sales_order.per_billed < 100:
		try:
			make_payment(woocommerce_order, sales_order)
			make_sales_invoice_from_sales_order(sales_order)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Woocommerce Payment and Invoice Error")

def make_payment(woocommerce_order, sales_order):
	frappe.flags.ignore_account_permission = True
	frappe.flags.ignore_permissions = True
	payment_entry = get_payment_entry(sales_order.doctype, sales_order.name)
	if payment_entry.paid_amount:
		payment_entry.reference_no = woocommerce_order.get("transaction_id") or woocommerce_order.get("payment_method_title")
		payment_entry.reference_date = woocommerce_order.get("date_paid")
		payment_entry.insert(ignore_permissions=True)
		payment_entry.submit()

def make_sales_invoice_from_sales_order(sales_order):
	si = make_sales_invoice(sales_order.name, ignore_permissions=True)
	si.allocate_advances_automatically = True
	si.insert(ignore_permissions=True)
	si.submit()

def create_update_order(data):
	wc_api = WooCommerceOrders()
	sync_order(wc_api, data)
	frappe.db.commit()