# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

no_cache = 1

from erpnext.e_commerce.shopping_cart.cart import get_cart_quotation
from erpnext.venue.doctype.booking_credit.booking_credit import get_balance
from erpnext.venue.utils import get_customer


def get_context(context):
	context.body_class = "product-page"
	context.update(get_cart_quotation())

	context.credits_balance = {}
	if any(item.is_free_item and item.item_booking for item in context.doc.items):
		context.credits_balance = get_balance(get_customer())
