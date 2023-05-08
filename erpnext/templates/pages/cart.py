# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

no_cache = 1

import frappe

from erpnext.e_commerce.shopping_cart.cart import get_cart_quotation
from erpnext.venue.doctype.item_booking.item_booking import get_availabilities


def get_context(context):
	context.no_cache = 1
	context.body_class = "product-page"
	context.update(get_cart_quotation())


@frappe.whitelist(allow_guest=True)
def get_availabilities_for_cart(item, start, end, uom=None):
	quotation = get_cart_quotation()

	booked_items = [item.item_booking for item in quotation.get("doc", {}).get("items")]
	availabilities = get_availabilities(item, start, end, uom)

	output = []
	for availability in availabilities:
		if not availability.get("number") or availability.get("id") in booked_items:
			output.append(availability)

	return output
