from collections import defaultdict

import frappe
from frappe.contacts.doctype.address.address import get_preferred_address
from frappe.utils import nowdate, cint, flt, now_datetime, add_days
from frappe import _
from frappe.utils.background_jobs import get_jobs

from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice, make_delivery_note
from erpnext.portal.product_configurator.utils import get_item_codes_by_attributes
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.customers import sync_customer, sync_guest_customers
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.products import get_simple_item
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.stock.stock_ledger import NegativeStockError

DELIVERY_STATUSES = ["shipped", "completed", "lpc_transit", "lpc_delivered"]

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
	if sync_order in get_jobs()[frappe.local.site]:
		return

	wc_api = WooCommerceOrders()

	woocommerce_orders = get_woocommerce_orders(wc_api)
	excluded_ids = get_completed_and_excluded_orders()
	closed_orders = get_closed_orders()

	for woocommerce_order in woocommerce_orders:
		if str(woocommerce_order.get("id")) in excluded_ids:
			continue
		elif (
			str(woocommerce_order.get("id")) in closed_orders
			and woocommerce_order.get("status") in ("failed", "refunded")
		):
			continue

		frappe.enqueue(sync_order, queue='long', wc_api=wc_api, woocommerce_order=woocommerce_order)

def sync_order(wc_api, woocommerce_order):
	if woocommerce_order.get("customer_id") == 0 and not woocommerce_order.get("billing", {}).get("email"):
		return

	customer = None

	if woocommerce_order.get("customer_id") != 0:
		customer = _sync_customer(wc_api, woocommerce_order.get("customer_id"))

	if not customer:
		customer = sync_guest_customers(woocommerce_order)

	if customer:
		try:
			if frappe.db.exists("Sales Order", dict(woocommerce_id=woocommerce_order.get("id"), docstatus=(">=", 1))):
				_update_sales_order(wc_api.settings, woocommerce_order, customer)
			else:
				_new_sales_order(wc_api.settings, woocommerce_order, customer)
		except Exception:
			frappe.log_error(f"WooCommerce Order: {woocommerce_order.get('id')}\n\n{frappe.get_traceback()}", "WooCommerce Order Sync Error")

def _sync_customer(wc_api, id):
	try:
		woocommerce_customer = wc_api.get(f"customers/{id}").json()
		return sync_customer(wc_api.settings, woocommerce_customer)
	except Exception as e:
		print("Woocommerce Customer Error", str(e))

def get_woocommerce_orders(wc_api):
	max_orders = wc_api.settings.max_orders
	per_page = 100
	documents_fetched = min(per_page, max_orders if max_orders else per_page)
	response = wc_api.get_orders(params={
		"per_page": documents_fetched,
		"dp": 4,
	})
	woocommerce_orders = response.json()

	if not max_orders or len(woocommerce_orders) < max_orders:
		for page_idx in range(2, cint(response.headers.get('X-WP-TotalPages')) + 1):
			if not max_orders or documents_fetched < cint(max_orders):
				response = wc_api.get_orders(params={
					"per_page": per_page,
					"page": page_idx,
					"dp": 4,
				})

				new_orders = response.json() if documents_fetched + len(response.json()) < cint(max_orders) or not max_orders else response.json()[:cint(max_orders) - documents_fetched]
				documents_fetched += per_page
				woocommerce_orders.extend(new_orders)

	return woocommerce_orders

def get_completed_and_excluded_orders():
	return frappe.get_all("Sales Order",
		filters={
			"woocommerce_id": ("is", "set"),
			"status": "Completed"
		},
		pluck="woocommerce_id"
	) + frappe.get_all("Woocommerce Excluded Order", pluck="name")

def get_closed_orders():
	return frappe.get_all("Sales Order",
		filters={
			"woocommerce_id": ("is", "set"),
			"status": "Closed"
		},
		pluck="woocommerce_id"
	)

def create_sales_order(settings, woocommerce_order, customer):
	return frappe.get_doc({
		"doctype": "Sales Order",
		"order_type": "Shopping Cart",
		"naming_series": settings.sales_order_series,
		"woocommerce_id": woocommerce_order.get("id"),
		"woocommerce_number": woocommerce_order.get("number"),
		"transaction_date": woocommerce_order.get("date_created_gmt") or nowdate(),
		"customer": customer.name,
		"customer_group": customer.customer_group,
		"delivery_date": add_days(woocommerce_order.get("date_created_gmt") or nowdate(), settings.delivery_after_days),
		"company": settings.company,
		"selling_price_list": settings.price_list,
		"ignore_pricing_rule": 1,
		"items": get_order_items(woocommerce_order, settings, woocommerce_order.get("date_created_gmt")),
		"taxes": get_order_taxes(woocommerce_order, settings),
		"currency": woocommerce_order.get("currency"),
		"taxes_and_charges": None,
		"customer_address": get_preferred_address("Customer", customer.name, "is_primary_address"),
		"shipping_address_name": get_preferred_address("Customer", customer.name, "is_shipping_address"),
		"disable_rounded_total": 0
	})

def _new_sales_order(settings, woocommerce_order, customer):
	so = create_sales_order(settings, woocommerce_order, customer)

	if so.items:
		try:
			if woocommerce_order.get("status") == "on-hold":
				so.status = "On Hold"
			so.flags.ignore_permissions = True
			so.insert()
			so.submit()
		except Exception as e:
			exclude_order(woocommerce_order, str(e))
			raise
	else:
		error = f"No items found for Woocommerce order {woocommerce_order.get('id')}"
		exclude_order(woocommerce_order, error)
		frappe.log_error(error, "Woocommerce Order Error")

def exclude_order(woocommerce_order, error=None):
	try:
		frappe.get_doc({
			"doctype": "Woocommerce Excluded Order",
			"woocommerce_id": woocommerce_order.get("id"),
			"data": frappe.as_json(woocommerce_order),
			"error": error
		}).insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		pass

def get_order_items(order, settings, delivery_date):
	items = []
	for item in order.get("line_items"):
		item_code = None

		if not flt(item.get("price")) and True in [x.get("key") == "_bundled_by" or x.get("key") == "_bundled_item_id" for x in item.get("meta_data")]:
			continue

		if not item.get("product_id"):
			item_code = get_or_create_missing_item(settings, item)

		if not item_code:
			item_code = get_item_code_and_warehouse(item)

		if item_code:
			warehouse = frappe.db.get_value("Item", item_code, "website_warehouse")
			stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
			items.append({
				"item_code": item_code,
				"rate": flt(item.get("price")),
				"is_free_item": not flt(item.get("price")),
				"delivery_date": delivery_date or nowdate(),
				"qty": item.get("quantity"),
				"warehouse": warehouse or settings.warehouse,
				"stock_uom": stock_uom,
				"uom": frappe.db.get_value("Item", item_code, "sales_uom") or stock_uom,
				"discount_percentage": 0.0 if flt(item.get("price")) else 100.0
			})
		else:
			frappe.log_error(f"Order: {order.get('id')}\n\nItem missing for Woocommerce product: {item.get('product_id')}", "Woocommerce Order Error")

	return items

def get_item_code_and_warehouse(item):
	if cint(item.get("variation_id")) > 0:
		item_code = frappe.db.get_value("Item", {"woocommerce_id": item.get("variation_id")}, "item_code")
	else:
		item_code = frappe.db.get_value("Item", {"woocommerce_id": item.get("product_id")}, "item_code")

		if item_code:
			has_variants = frappe.db.get_value("Item", {"woocommerce_id": item.get("product_id")}, "has_variants")

			if cint(has_variants) and len(item.get("meta_data")):
				variants = get_item_codes_by_attributes({x.get("display_key"): x.get("value") for x in item.get("meta_data") if isinstance(x.get("value"), str)}, item_code)
				if variants:
					item_code = variants[0]

	return item_code

def get_or_create_missing_item(settings, product):
	item = frappe.db.get_value("Item", product.get("name"))

	if not item:
		item_doc = frappe.get_doc(
			get_simple_item(settings, {
				"name": product.get("name"),
				"categories": []
			})
		)
		try:
			item_doc.insert(ignore_permissions=True)
		except frappe.exceptions.DuplicateEntryError:
			pass

		if item_doc:
			item = item_doc.name

	return item

def get_order_taxes(order, settings):
	taxes = []
	line_item_taxes = defaultdict(lambda: defaultdict(float))
	for item in order.get("line_items", []) + order.get("shipping_lines", []):
		for item_tax in item.get("taxes"):
			account_head = get_tax_account_head(item_tax.get("id"))
			if account_head:
				line_item_taxes[account_head]["id"] = item_tax.get("id")
				line_item_taxes[account_head]["total"] += flt(item_tax.get("total"), precision=9)
			else:
				frappe.log_error(f"WooCommerce Order: {order.get('id')}\n\nAccount head missing for Woocommerce tax: {item_tax.get('id')}", "Woocommerce Order Error")

	for account_head in line_item_taxes:
		taxes.append({
			"charge_type": "Actual",
			"account_head": account_head,
			"description": get_label_from_wc_tax_summary(order, line_item_taxes[account_head]["id"]),
			"rate": 0,
			"tax_amount": flt(line_item_taxes[account_head]["total"], precision=9), #flt(tax.get("tax_total") or 0) + flt(tax.get("shipping_tax_total") or 0),
			"included_in_print_rate": 0,
			"cost_center": settings.cost_center
		})

	taxes = update_taxes_with_shipping_lines(order, taxes, order.get("shipping_lines"), settings)
	taxes = update_taxes_with_fee_lines(taxes, order.get("fee_lines"), settings)

	return taxes

def get_label_from_wc_tax_summary(order, id):
	for tax in order.get("tax_lines"):
		if tax.get("rate_id") == id:
			return tax.get("label")

def update_taxes_with_fee_lines(taxes, fee_lines, settings):
	for fee_charge in fee_lines:
		taxes.insert(0, {
			"charge_type": "Actual",
			"account_head": settings.fee_account,
			"description": fee_charge["name"],
			"tax_amount": fee_charge["amount"],
			"cost_center": settings.cost_center
		})

	return taxes

def update_taxes_with_shipping_lines(order, taxes, shipping_lines, settings):
	for shipping_charge in shipping_lines:
		if shipping_charge.get('method_id'):
			account_head = get_shipping_account_head(shipping_charge.get("method_id"))

			if account_head:
				taxes.insert(0, {
					"charge_type": "Actual",
					"account_head": account_head,
					"description": shipping_charge.get("method_title"),
					"tax_amount": shipping_charge.get("total"),
					"cost_center": settings.cost_center
				})
			else:
				frappe.log_error(f"WooCommerce Order: {order.get('id')}\n\nAccount head missing for Woocommerce shipping method: {shipping_charge.get('method_id')}", "Woocommerce Order Error")

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
	original_so = frappe.get_doc("Sales Order", dict(woocommerce_id=woocommerce_order.get("id")))
	if original_so.status == "Completed":
		return

	elif original_so.status == "Closed":
		if woocommerce_order.get("status") in ("failed", "refunded"):
			return
		else:
			original_so.update_status("Draft")

	if woocommerce_order.get("status") == "cancelled":
		if original_so.docstatus == 1:
			original_so.cancel()
		return

	if original_so.docstatus == 2 and woocommerce_order.get("status") != "cancelled":
		return frappe.db.set_value("Sales Order", original_so.name, "docstatus", 1)

	updated_so = create_sales_order(settings, woocommerce_order, customer)
	sales_order = original_so

	so_are_similar = compare_sales_orders(original_so, updated_so)

	if not so_are_similar and not (flt(original_so.per_delivered) or flt(original_so.per_billed)):
		try:
			if original_so.docstatus == 1:
				original_so.flags.ignore_permissions = True
				original_so.cancel()

			sales_order = updated_so
			sales_order.flags.ignore_permissions = True
			sales_order.insert()
			sales_order.submit()
			frappe.db.commit()
		except Exception:
			# Usually this throws an exception when the original so can't be cancelled
			pass

	if sales_order:
		update_so_status(sales_order, woocommerce_order)

		if cint(settings.create_payments_and_sales_invoice):
			if woocommerce_order.get("status") == "refunded":
				refund_sales_order(settings, woocommerce_order, sales_order)
			elif woocommerce_order.get("date_paid") or (
				woocommerce_order.get("payment_method") and woocommerce_order.get("status") in DELIVERY_STATUSES
			):
				# Delivered sales orders with a payment method are assumed to be paid
				register_payment_and_invoice(woocommerce_order, sales_order)

		if woocommerce_order.get("status") in DELIVERY_STATUSES:
			register_delivery(settings, woocommerce_order, sales_order)

def update_so_status(sales_order, woocommerce_order):
	sales_order.reload()
	if woocommerce_order.get("status") == "on-hold":
		sales_order.update_status("On Hold")
	elif sales_order.status == "On Hold":
		sales_order.reload()
		sales_order.update_status("Draft")
	elif woocommerce_order.get("status") == "failed":
		sales_order.update_status("Closed")

def compare_sales_orders(original, updated):
	if not updated.items:
		return True

	if original.docstatus == 2:
		return False

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

def register_payment_and_invoice(woocommerce_order, sales_order):
	# Keep 99.99 because of rounding issues
	if flt(sales_order.per_billed) < 99.99 and sales_order.docstatus == 1:
		try:
			if sales_order.status in ("On Hold", "Closed"):
				frappe.db.set_value("Sales Order", sales_order.name, "status", "To Bill")

			make_payment(woocommerce_order, sales_order)
			make_sales_invoice_from_sales_order(woocommerce_order, sales_order)
		except Exception:
			frappe.log_error(f"WooCommerce Order: {woocommerce_order.get('id')}\nSales Order: {sales_order.name}\n\n{frappe.get_traceback()}", "Woocommerce Payment and Invoice Error")

def make_payment(woocommerce_order, sales_order):
	if flt(sales_order.advance_paid) < flt(sales_order.grand_total) and woocommerce_order.get("transaction_id") and not frappe.get_all("Payment Entry", dict(reference_no=woocommerce_order.get("transaction_id"))):
		frappe.flags.ignore_account_permission = True
		frappe.flags.ignore_permissions = True
		payment_entry = get_payment_entry(sales_order.doctype, sales_order.name)
		if payment_entry.paid_amount:
			if woocommerce_order.get("payment_method") == "stripe":
				add_stripe_fees(woocommerce_order, payment_entry)
			payment_entry.posting_date = woocommerce_order.get("date_paid")
			payment_entry.reference_no = woocommerce_order.get("transaction_id") or woocommerce_order.get("payment_method_title") or "WooCommerce Order"
			payment_entry.reference_date = woocommerce_order.get("date_paid")
			payment_entry.insert(ignore_permissions=True)

			if payment_entry.difference_amount:
				payment_entry.append("deductions", {
					"account": frappe.db.get_value("Company", sales_order.company, "write_off_account"),
					"cost_center": sales_order.cost_center or frappe.db.get_value("Company", payment_entry.company, "cost_center"),
					"amount": payment_entry.difference_amount
				})
			payment_entry.submit()

def add_stripe_fees(woocommerce_order, payment_entry):
	settings = frappe.get_single("Woocommerce Settings")
	if not settings.stripe_gateway:
		return

	stripe_gateway = frappe.get_doc("Payment Gateway", settings.stripe_gateway)
	if not stripe_gateway.fee_account:
		return

	keys = ["_stripe_fee", "_stripe_net", "_stripe_currency", "_stripe_charge_captured"]
	charge = defaultdict(str)
	for meta in woocommerce_order.get("meta_data"):
		if meta.get("key") in keys:
			charge[meta.get("key")] = meta.get("value")

	if not charge.get("_stripe_charge_captured") and not charge.get("_stripe_charge_captured") == "yes":
		return

	payment_entry.update({
		"paid_amount": flt(charge.get("_stripe_net")),
		"received_amount": flt(charge.get("_stripe_net"))
	})

	payment_entry.append("deductions", {
		"account": stripe_gateway.fee_account,
		"cost_center": stripe_gateway.cost_center or frappe.db.get_value("Company", payment_entry.company, "cost_center"),
		"amount": flt(charge.get("_stripe_fee"))
	})

def make_sales_invoice_from_sales_order(woocommerce_order, sales_order):
	if not frappe.db.sql(f"""
			select
				si.name
			from
				`tabSales Invoice` si, `tabSales Invoice Item` si_item
			where
				si.name = si_item.parent
				and si_item.sales_order = {frappe.db.escape(sales_order.name)}
				and si.docstatus = 0
		"""):
		si = make_sales_invoice(sales_order.name, ignore_permissions=True)
		si.set_posting_time = True
		si.posting_date = woocommerce_order.get("date_paid")
		si.allocate_advances_automatically = True
		si.insert(ignore_permissions=True)
		si.submit()

def register_delivery(settings, woocommerce_order, sales_order):
	if flt(sales_order.per_delivered) < 100:
		_make_delivery_note(woocommerce_order, sales_order)

def _make_delivery_note(woocommerce_order, sales_order):
	frappe.set_user("administrator")
	dn = make_delivery_note(sales_order.name)
	dn.set_posting_time = True
	dn.posting_date = woocommerce_order.get("date_completed")
	dn.run_method('set_missing_values')
	dn.insert(ignore_permissions=True)
	try:
		dn.submit()
	except NegativeStockError:
		pass

def refund_sales_order(settings, woocommerce_order, sales_order):
	sales_invoices = frappe.get_all("Sales Invoice Item",
		filters={"sales_order": sales_order.name},
		pluck="parent"
	)

	for sales_invoice in sales_invoices:
		cn = make_sales_return(sales_invoice)
		cn.flags.ignore_permissions = True
		cn.insert()
		cn.submit()

		payment_entry = get_payment_entry("Sales Invoice", cn.name)
		if payment_entry.paid_amount:
			payment_entry.reference_no = woocommerce_order.get("transaction_id") or woocommerce_order.get("payment_method_title") or "WooCommerce Order"
			payment_entry.reference_date = woocommerce_order.get("date_paid")
			payment_entry.insert(ignore_permissions=True)
			payment_entry.submit()

	else:
		frappe.db.set_value("Sales Order", sales_order.name, "status", "Closed")

def create_update_order(data):
	wc_api = WooCommerceOrders()
	sync_order(wc_api, data)
	frappe.db.commit()
