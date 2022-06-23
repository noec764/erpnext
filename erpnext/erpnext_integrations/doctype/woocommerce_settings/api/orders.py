from collections import defaultdict
from datetime import datetime

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_preferred_address
from frappe.utils import (
	add_days,
	add_to_date,
	add_years,
	cint,
	flt,
	get_datetime,
	get_time_zone,
	now_datetime,
	nowdate,
)
from frappe.utils.background_jobs import get_jobs
from pytz import timezone

from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.e_commerce.variant_selector.utils import get_item_codes_by_attributes
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.bookings import (
	WooCommerceBookingsAPI,
)
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.customers import (
	sync_customer,
	sync_guest_customers,
)
from erpnext.erpnext_integrations.doctype.woocommerce_settings.api.products import get_simple_item
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice
from erpnext.stock.stock_ledger import NegativeStockError

DELIVERY_STATUSES = ["shipped", "completed", "lpc_transit", "lpc_delivered"]


class WooCommerceOrdersAPI(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceOrdersAPI, self).__init__(version, args, kwargs)

	def get_orders(self, params=None):
		return self.get("orders", params=params)


class WooCommerceTaxesAPI(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceTaxesAPI, self).__init__(version, args, kwargs)

	def get_tax(self, id, params=None):
		return self.get(f"taxes/{id}", params=params).json()

	def get_taxes(self, params=None):
		return self.get("taxes", params=params).json()


class WooCommerceShippingMethodsAPI(WooCommerceAPI):
	def __init__(self, version="wc/v3", *args, **kwargs):
		super(WooCommerceShippingMethodsAPI, self).__init__(version, args, kwargs)

	def get_shipping_methods(self, params=None):
		return self.get("shipping_methods", params=params).json()


def create_update_order(data):
	WooCommerceOrderSync(WooCommerceOrdersAPI(), data).sync()
	frappe.db.commit()


def sync_orders():
	if sync_order in get_jobs()[frappe.local.site]:
		return

	WooCommerceOrdersSync()


class WooCommerceOrdersSync:
	def __init__(self):
		self.wc_api = WooCommerceOrdersAPI()
		self.woocommerce_orders = []

		self.get_woocommerce_orders()
		for woocommerce_order in self.woocommerce_orders:
			if frappe.conf.developer_mode:
				sync_order(self.wc_api, woocommerce_order)
			else:
				frappe.enqueue(
					sync_order, queue="long", wc_api=self.wc_api, woocommerce_order=woocommerce_order
				)

		self.set_synchronization_datetime()

	def get_woocommerce_orders(self):
		woocommerce_time_zone = self.wc_api.settings.woocommerce_site_timezone or "UTC"
		user_time_zone = get_time_zone()
		last_modified_timestamp = get_datetime(
			self.wc_api.settings.last_synchronization_datetime or add_years(now_datetime(), -99)
		)
		localized_timestamp = timezone(user_time_zone).localize(last_modified_timestamp)
		woocommerce_timestamp = localized_timestamp.astimezone(timezone(woocommerce_time_zone))
		per_page = 100
		response = self.wc_api.get_orders(
			params={
				"per_page": per_page,
				"modified_after": woocommerce_timestamp,
				"dp": 4,
			}
		)
		self.woocommerce_orders = response.json()

		for page_idx in range(2, cint(response.headers.get("X-WP-TotalPages")) + 1):
			response = self.wc_api.get_orders(
				params={
					"per_page": per_page,
					"modified_after": woocommerce_timestamp,
					"dp": 4,
					"page": page_idx,
				}
			)
			self.woocommerce_orders.extend(response.json())

	def set_synchronization_datetime(self):
		frappe.db.set_value(
			"Woocommerce Settings",
			None,
			"last_synchronization_datetime",
			frappe.utils.get_datetime_str(add_to_date(now_datetime(), minutes=-1)),
		)


def sync_order(wc_api, woocommerce_order):
	WooCommerceOrderSync(wc_api, woocommerce_order).sync()


class WooCommerceOrderSync:
	def __init__(self, wc_api, woocommerce_order):
		self.woocommerce_order = woocommerce_order
		self.wc_api = wc_api
		self.settings = self.wc_api.settings
		self.customer = None
		self.sales_order = None
		self.bookings = []

	def sync(self):
		# Excluded orders need to be synced manually
		# Completed orders and closed orders refunded or failed don't need to be synchronized again
		if self.is_excluded_order() or self.is_completed_order() or self.is_closed_order():
			return

		if self.woocommerce_order.get("customer_id") == 0 and not self.woocommerce_order.get(
			"billing", {}
		).get("email"):
			return

		self.get_customer()

		if self.customer:
			try:
				if frappe.db.exists(
					"Sales Order", dict(woocommerce_id=self.woocommerce_order.get("id"), docstatus=1)
				):
					self._update_sales_order()
				else:
					self._new_sales_order()
			except Exception:
				msg = _("WooCommerce Order: {0}\n\n{1}").format(
					self.woocommerce_order.get("id"), frappe.get_traceback()
				)
				frappe.log_error(
					message=msg,
					title=_("WooCommerce Order Sync Error"),
				)

	def is_excluded_order(self):
		return frappe.db.exists("Woocommerce Excluded Order", self.woocommerce_order.get("id"))

	def is_completed_order(self):
		return frappe.db.exists(
			"Sales Order",
			{"woocommerce_id": self.woocommerce_order.get("id"), "status": "Completed", "docstatus": 1},
		)

	def is_closed_order(self):
		return frappe.db.exists(
			"Sales Order",
			{"woocommerce_id": self.woocommerce_order.get("id"), "status": "Closed", "docstatus": 1},
		) and self.woocommerce_order.get("status") in ("failed", "refunded")

	def get_customer(self):
		if self.woocommerce_order.get("customer_id") != 0:
			self._sync_customer(self.woocommerce_order.get("customer_id"))

		if not self.customer:
			self.customer = sync_guest_customers(self.woocommerce_order)

	def _sync_customer(self, id):
		woocommerce_customer = self.wc_api.get(f"customers/{id}").json()
		self.customer = sync_customer(self.settings, woocommerce_customer)

	def _update_sales_order(self):
		original_so = frappe.get_doc(
			"Sales Order", dict(woocommerce_id=self.woocommerce_order.get("id"), docstatus=1)
		)
		if original_so.status == "Closed":
			original_so.update_status("Draft")

		if self.woocommerce_order.get("status") == "cancelled":
			original_so.cancel()

		# TODO: check if that can happen
		# if original_so.docstatus == 2 and self.woocommerce_order.get("status") != "cancelled":
		# 	return frappe.db.set_value("Sales Order", original_so.name, "docstatus", 1)

		updated_so = self.create_sales_order()
		self.sales_order = original_so

		so_are_similar = compare_sales_orders(original_so, updated_so)

		if not so_are_similar and not (flt(original_so.per_delivered) or flt(original_so.per_billed)):
			try:
				original_so.flags.ignore_permissions = True
				original_so.cancel()

				self.sales_order = updated_so
				self.sales_order.flags.ignore_permissions = True
				self.sales_order.insert()
				self.sales_order.submit()
			except Exception:
				# Usually this throws an exception when the original so can't be cancelled
				pass

		if self.sales_order:
			self.update_so_status()

			if cint(self.wc_api.settings.create_payments_and_sales_invoice):
				if self.woocommerce_order.get("status") == "refunded":
					self.refund_sales_order()
				elif self.woocommerce_order.get("date_paid") or (
					self.woocommerce_order.get("payment_method")
					and self.woocommerce_order.get("status") in DELIVERY_STATUSES
				):
					# Delivered sales orders with a payment method are assumed to be paid
					self.register_payment_and_invoice()

			if self.woocommerce_order.get("status") in DELIVERY_STATUSES:
				self.register_delivery()

	def update_so_status(self):
		self.sales_order.reload()
		if self.woocommerce_order.get("status") == "on-hold":
			self.sales_order.update_status("On Hold")
			self.update_booking_status("Not Confirmed")
		elif self.sales_order.status == "On Hold":
			self.sales_order.reload()
			self.sales_order.update_status("Draft")
		elif self.woocommerce_order.get("status") == "failed":
			self.sales_order.update_status("Closed")
			self.update_booking_status("Cancelled")

	def update_booking_status(self, status):
		for item in self.sales_order.items:
			if item.item_booking:
				frappe.db.set_value("Item Booking", item.item_booking, "status", status)

	def _new_sales_order(self):
		so = self.create_sales_order()

		if so.items:
			try:
				if self.woocommerce_order.get("status") == "on-hold":
					so.status = "On Hold"
				so.flags.ignore_permissions = True
				so.insert()
				so.submit()
			except Exception as e:
				self.exclude_order(str(e))
				raise
		else:
			error = f"No items found for Woocommerce order {self.woocommerce_order.get('id')}"
			self.exclude_order(error)
			so.log_error(message=error, title=_("Woocommerce Order Error"))

	def exclude_order(self, error=None):
		frappe.get_doc(
			{
				"doctype": "Woocommerce Excluded Order",
				"woocommerce_id": self.woocommerce_order.get("id"),
				"data": frappe.as_json(self.woocommerce_order),
				"error": error,
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

	def create_sales_order(self):
		delivery_date = add_days(
			self.woocommerce_order.get("date_created_gmt") or nowdate(), self.settings.delivery_after_days
		)
		return frappe.get_doc(
			{
				"doctype": "Sales Order",
				"order_type": "Shopping Cart",
				"naming_series": self.settings.sales_order_series,
				"woocommerce_id": self.woocommerce_order.get("id"),
				"woocommerce_number": self.woocommerce_order.get("number"),
				"transaction_date": self.woocommerce_order.get("date_created_gmt") or nowdate(),
				"customer": self.customer.name,
				"customer_group": self.customer.customer_group,
				"delivery_date": delivery_date,
				"company": self.settings.company,
				"selling_price_list": self.settings.price_list,
				"ignore_pricing_rule": 1,
				"items": self.get_order_items(delivery_date),
				"taxes": self.get_order_taxes(),
				"currency": self.woocommerce_order.get("currency"),
				"taxes_and_charges": None,
				"customer_address": get_preferred_address(
					"Customer", self.customer.name, "is_primary_address"
				),
				"shipping_address_name": get_preferred_address(
					"Customer", self.customer.name, "is_shipping_address"
				),
				"disable_rounded_total": 0,
			}
		)

	def get_order_items(self, delivery_date):
		items = []
		for item in self.woocommerce_order.get("line_items"):
			item_code = None

			if not flt(item.get("price")) and True in [
				x.get("key") == "_bundled_by" or x.get("key") == "_bundled_item_id"
				for x in item.get("meta_data")
			]:
				continue

			if not item.get("product_id"):
				item_code = self.get_or_create_missing_item(self.settings, item)

			if not item_code:
				item_code = self.get_item_code_and_warehouse(item)

			if item_code:
				warehouse = frappe.db.get_value("Website Item", dict(item_code=item_code), "website_warehouse")
				item_data = frappe.db.get_value(
					"Item", item_code, ("stock_uom", "enable_item_booking"), as_dict=True
				)

				items.append(
					{
						"item_code": item_code,
						"rate": flt(item.get("price")),
						"is_free_item": not flt(item.get("price")),
						"delivery_date": delivery_date,
						"qty": item.get("quantity"),
						"warehouse": warehouse or self.settings.warehouse,
						"stock_uom": item_data.get("stock_uom"),
						"uom": frappe.db.get_value("Item", item_code, "sales_uom") or item_data.get("stock_uom"),
						"discount_percentage": 0.0 if flt(item.get("price")) else 100.0,
						"item_booking": self.get_booking_for_line_item(item, item_code)
						if item_data.get("enable_item_booking")
						else None,
					}
				)
			else:
				frappe.log_error(
					message=_("Item missing for Woocommerce product: {0}").format(item.get("product_id")),
					title=_("Woocommerce Order Error"),
				)

		return items

	def get_item_code_and_warehouse(self, item):
		if cint(item.get("variation_id")) > 0:
			item_code = frappe.db.get_value(
				"Item", {"woocommerce_id": item.get("variation_id")}, "item_code"
			)
		else:
			item_code = frappe.db.get_value("Item", {"woocommerce_id": item.get("product_id")}, "item_code")

			if item_code:
				has_variants = frappe.db.get_value(
					"Item", {"woocommerce_id": item.get("product_id")}, "has_variants"
				)

				if cint(has_variants) and len(item.get("meta_data")):
					variants = get_item_codes_by_attributes(
						{
							x.get("display_key"): x.get("value")
							for x in item.get("meta_data")
							if isinstance(x.get("value"), str)
						},
						item_code,
					)
					if variants:
						item_code = variants[0]

		return item_code

	def get_or_create_missing_item(self, product):
		item = frappe.db.get_value("Item", product.get("name"))

		if not item:
			item_doc = frappe.get_doc(
				get_simple_item(self.settings, {"name": product.get("name"), "categories": []})
			)
			item_doc.insert(ignore_permissions=True, ignore_if_duplicate=True)

			if item_doc:
				item = item_doc.name

		return item

	def get_booking_for_line_item(self, line_item, item_code):
		if not self.bookings:
			self.get_woocommerce_bookings()

		for booking in self.bookings:
			if booking.get("order_item_id") == line_item.get("id"):
				return self.create_update_item_booking(booking, item_code)

	def get_woocommerce_bookings(self):
		# TODO: implement a request filtered by order as soon as it is available on WooCoommerce side
		try:
			bookings = (
				WooCommerceBookingsAPI()
				.get_bookings(
					params={"after": add_to_date(self.woocommerce_order.get("date_created"), hours=-1)}
				)
				.json()
				or []
			)

			self.bookings = [b for b in bookings if b.get("order_id") == self.woocommerce_order.get("id")]
		except Exception:
			self.bookings = []

	def create_update_item_booking(self, booking, item_code):
		existing_booking = frappe.db.get_value("Item Booking", dict(woocommerce_id=booking.get("id")))
		if existing_booking:
			doc = frappe.get_doc("Item Booking", existing_booking)
		else:
			doc = frappe.new_doc("Item Booking")
			doc.woocommerce_id = booking.get("id")

		doc.starts_on = datetime.fromtimestamp(booking.get("start"))
		doc.ends_on = datetime.fromtimestamp(booking.get("end"))
		doc.all_day = booking.get("all_day")
		doc.status = (
			"Confirmed"
			if booking.get("status") in ("paid", "confirmed", "complete")
			else ("Cancelled" if booking.get("status") == "cancelled" else "Not Confirmed")
		)
		doc.item = item_code
		doc.google_calendar_event_id = booking.get("google_calendar_event_id")
		doc.insert(ignore_permissions=True)

		return doc.name

	def get_order_taxes(self):
		taxes = []
		line_item_taxes = defaultdict(lambda: defaultdict(float))
		for item in self.woocommerce_order.get("line_items", []) + self.woocommerce_order.get(
			"shipping_lines", []
		):
			for item_tax in item.get("taxes"):
				account_head = self.get_tax_account_head(item_tax.get("id"))
				if account_head:
					line_item_taxes[account_head]["id"] = item_tax.get("id")
					line_item_taxes[account_head]["total"] += flt(item_tax.get("total"), precision=9)
				else:
					frappe.log_error(
						f"WooCommerce Order: {self.woocommerce_order.get('id')}\n\nAccount head missing for Woocommerce tax: {item_tax.get('id')}",
						"Woocommerce Order Error",
					)

		for account_head in line_item_taxes:
			taxes.append(
				{
					"charge_type": "Actual",
					"account_head": account_head,
					"description": self.get_label_from_wc_tax_summary(line_item_taxes[account_head]["id"]),
					"rate": 0,
					"tax_amount": flt(
						line_item_taxes[account_head]["total"], precision=9
					),  # flt(tax.get("tax_total") or 0) + flt(tax.get("shipping_tax_total") or 0),
					"included_in_print_rate": 0,
					"cost_center": self.settings.cost_center,
				}
			)

		taxes = self.update_taxes_with_shipping_lines(taxes)
		taxes = self.update_taxes_with_fee_lines(taxes)

		return taxes

	def get_label_from_wc_tax_summary(self, id):
		for tax in self.woocommerce_order.get("tax_lines"):
			if tax.get("rate_id") == id:
				return tax.get("label")

	def update_taxes_with_fee_lines(self, taxes):
		for fee_charge in self.woocommerce_order.get("fee_lines"):
			taxes.insert(
				0,
				{
					"charge_type": "Actual",
					"account_head": self.settings.fee_account,
					"description": fee_charge["name"],
					"tax_amount": fee_charge["amount"],
					"cost_center": self.settings.cost_center,
				},
			)

		return taxes

	def update_taxes_with_shipping_lines(self, taxes):
		for shipping_charge in self.woocommerce_order.get("shipping_lines"):
			if shipping_charge.get("method_id"):
				account_head = self.get_shipping_account_head(shipping_charge.get("method_id"))

				if account_head:
					taxes.insert(
						0,
						{
							"charge_type": "Actual",
							"account_head": account_head,
							"description": shipping_charge.get("method_title"),
							"tax_amount": shipping_charge.get("total"),
							"cost_center": self.settings.cost_center,
						},
					)
				else:
					self.woocommerce_order.log_error(
						message=_(
							"WooCommerce Order: {0}\n\nAccount head missing for Woocommerce shipping method: {1}"
						).format(
							self.woocommerce_order.get("id"), shipping_charge.get("method_id")
						),
						title=_("Woocommerce Order Error"),
					)

		return taxes

	@staticmethod
	def get_tax_account_head(id):
		accounts = frappe.get_all(
			"Woocommerce Taxes", filters=dict(woocommerce_tax_id=id), fields=["account"], limit=1
		)
		if accounts:
			return accounts[0].account

	@staticmethod
	def get_shipping_account_head(id):
		accounts = frappe.get_all(
			"Woocommerce Shipping Methods",
			filters=dict(woocommerce_shipping_method_id=id),
			fields=["account"],
			limit=1,
		)
		if accounts:
			return accounts[0].account

	def refund_sales_order(self):
		sales_invoices = frappe.get_all(
			"Sales Invoice Item", filters={"sales_order": self.sales_order.name}, pluck="parent"
		)

		for sales_invoice in sales_invoices:
			cn = make_sales_return(sales_invoice)
			cn.flags.ignore_permissions = True
			cn.insert()
			cn.submit()

			payment_entry = get_payment_entry("Sales Invoice", cn.name)
			if payment_entry.paid_amount:
				payment_entry.reference_no = (
					self.woocommerce_order.get("transaction_id")
					or self.woocommerce_order.get("payment_method_title")
					or _("WooCommerce Order")
				)
				payment_entry.reference_date = self.woocommerce_order.get("date_paid")
				payment_entry.insert(ignore_permissions=True)
				payment_entry.submit()

		else:
			frappe.db.set_value("Sales Order", self.sales_order.name, "status", "Closed")

	def register_payment_and_invoice(self):
		# Keep 99.99 because of rounding issues
		if flt(self.sales_order.per_billed) < 99.99 and self.sales_order.docstatus == 1:
			try:
				if self.sales_order.status in ("On Hold", "Closed"):
					frappe.db.set_value("Sales Order", self.sales_order.name, "status", "To Bill")

				self.make_payment()
				self.make_sales_invoice_from_sales_order()
			except Exception:
				self.sales_order.log_error(
					message=_("WooCommerce Order: {0}\n\n{1}").format(
						self.woocommerce_order.get("id"), frappe.get_traceback()
					),
					title=_("Woocommerce Payment and Invoice Error"),
				)

	def register_delivery(self):
		if flt(self.sales_order.per_delivered) < 100:
			self._make_delivery_note()

	def _make_delivery_note(self):
		frappe.set_user("administrator")
		dn = make_delivery_note(self.sales_order.name)
		dn.set_posting_time = True
		dn.posting_date = self.woocommerce_order.get("date_completed")
		dn.run_method("set_missing_values")
		dn.insert(ignore_permissions=True)
		try:
			dn.submit()
		except NegativeStockError:
			pass

	def make_payment(self):
		if (
			flt(self.sales_order.advance_paid) < flt(self.sales_order.grand_total)
			and self.woocommerce_order.get("transaction_id")
			and not frappe.get_all(
				"Payment Entry", dict(reference_no=self.woocommerce_order.get("transaction_id"))
			)
		):
			frappe.flags.ignore_account_permission = True
			frappe.flags.ignore_permissions = True
			payment_entry = get_payment_entry(self.sales_order.doctype, self.sales_order.name)
			if payment_entry.paid_amount:
				if self.woocommerce_order.get("payment_method") == "stripe":
					self.add_stripe_fees(payment_entry)
				payment_entry.posting_date = self.woocommerce_order.get("date_paid")
				payment_entry.reference_no = (
					self.woocommerce_order.get("transaction_id")
					or self.woocommerce_order.get("payment_method_title")
					or _("WooCommerce Order")
				)
				payment_entry.reference_date = self.woocommerce_order.get("date_paid")
				payment_entry.insert(ignore_permissions=True)

				if payment_entry.difference_amount:
					payment_entry.append(
						"deductions",
						{
							"account": frappe.db.get_value("Company", self.sales_order.company, "write_off_account"),
							"cost_center": self.sales_order.cost_center
							or frappe.db.get_value("Company", payment_entry.company, "cost_center"),
							"amount": payment_entry.difference_amount,
						},
					)
				payment_entry.submit()

	def add_stripe_fees(self, payment_entry):
		settings = frappe.get_single("Woocommerce Settings")
		if not settings.stripe_gateway:
			return

		stripe_gateway = frappe.get_doc("Payment Gateway", settings.stripe_gateway)
		if not stripe_gateway.fee_account:
			return

		keys = ["_stripe_fee", "_stripe_net", "_stripe_currency", "_stripe_charge_captured"]
		charge = defaultdict(str)
		for meta in self.woocommerce_order.get("meta_data"):
			if meta.get("key") in keys:
				charge[meta.get("key")] = meta.get("value")

		if (
			not charge.get("_stripe_charge_captured") and not charge.get("_stripe_charge_captured") == "yes"
		):
			return

		payment_entry.update(
			{
				"paid_amount": flt(charge.get("_stripe_net")),
				"received_amount": flt(charge.get("_stripe_net")),
			}
		)

		payment_entry.append(
			"deductions",
			{
				"account": stripe_gateway.fee_account,
				"cost_center": stripe_gateway.cost_center
				or frappe.db.get_value("Company", payment_entry.company, "cost_center"),
				"amount": flt(charge.get("_stripe_fee")),
			},
		)

	def make_sales_invoice_from_sales_order(self):
		if not frappe.db.sql(
			f"""
				select
					si.name
				from
					`tabSales Invoice` si, `tabSales Invoice Item` si_item
				where
					si.name = si_item.parent
					and si_item.sales_order = {frappe.db.escape(self.sales_order.name)}
					and si.docstatus = 0
			"""
		):
			si = make_sales_invoice(self.sales_order.name, ignore_permissions=True)
			si.set_posting_time = True
			si.posting_date = self.woocommerce_order.get("date_paid")
			si.allocate_advances_automatically = True
			si.insert(ignore_permissions=True)
			si.submit()


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
