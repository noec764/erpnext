# Copyright (c) 2023, Dokos SAS and Contributors
# License: GNU General Public License v3. See license.txt
import frappe
from frappe import _
from frappe.utils import getdate, get_datetime

from erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings import get_shopping_cart_settings
from erpnext.venue.doctype.item_booking.item_booking import get_availabilities

def get_context(context):
	context.no_cache = 1
	context.show_sidebar = True

	if frappe.session.user == "Guest":
		frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)


@frappe.whitelist()
def get_item_groups():
	return frappe.get_all(
		"Website Item",
		filters={
			"enable_item_booking": 1
		},
		distinct=True,
		pluck="item_group"
	)

@frappe.whitelist()
def get_items(filters=None):
	if filters:
		filters = frappe.parse_json(filters)

	fields = [
		"web_item_name",
		"name",
		"item_name",
		"item_code",
		"website_image",
		"variant_of",
		"has_variants",
		"item_group",
		"web_long_description",
		"short_description",
		"route",
		"website_warehouse",
		"ranking",
		"on_backorder",
		"enable_item_booking",
		"no_add_to_cart"
	]

	query_filters = {
		"enable_item_booking": 1
	}
	if filters.get("item_groups"):
		query_filters["item_group"] = ("in", filters.get("item_groups"))

	items = frappe.get_all("Website Item", filters=query_filters, fields=fields)

	if filters.get("start_date") and filters.get("end_date"):
		for item in items:
			item.availabilities = get_availabilities(item.item_code, get_datetime(filters.get("start_date")), get_datetime(filters.get("end_date")))

	return {
		"items": items,
		"settings": get_shopping_cart_settings()
	}