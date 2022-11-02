import frappe


def execute():
	if frappe.db.has_table("E Commerce Settings"):
		return

	frappe.reload_doc("e-commerce", "doctype", "e commerce settings")

	shopping_cart = frappe._dict(
		{
			x["field"]: x["value"]
			for x in frappe.db.sql(
				"""SELECT * FROM `tabSingles` WHERE doctype='Shopping Cart Settings'""", as_dict=True
			)
		}
	)
	if not shopping_cart.enabled:
		return

	product_settings = frappe._dict(
		{
			x["field"]: x["value"]
			for x in frappe.db.sql(
				"""SELECT * FROM `tabSingles` WHERE doctype='Product Settings'""", as_dict=True
			)
		}
	)

	ecommerce = frappe.get_single("E Commerce Settings")

	ecommerce.update(
		{
			"products_per_page": product_settings.products_per_page or 6,
			"enable_variants": shopping_cart.enable_variants,
			"show_price": shopping_cart.show_price,
			"show_stock_availability": shopping_cart.show_stock_availability,
			"allow_items_not_in_stock": shopping_cart.allow_items_not_in_stock,
			"show_apply_coupon_code_in_website": shopping_cart.show_apply_coupon_code_in_website,
			"show_contact_us_button": shopping_cart.show_contact_us_button,
			"show_attachments": shopping_cart.show_attachments,
			"company": shopping_cart.company,
			"price_list": shopping_cart.price_list,
			"enabled": 1,
			"default_customer_group": shopping_cart.default_customer_group,
			"quotation_series": shopping_cart.quotation_series,
			"enable_checkout": shopping_cart.enable_checkout,
			"show_price_in_quotation": shopping_cart.show_price,
			"no_payment_gateway": shopping_cart.no_payment_gateway,
			"payment_gateway_account": shopping_cart.payment_gateway_account,
			"payment_success_url": shopping_cart.payment_success_url,
		}
	)

	ecommerce.save()

	for item in frappe.get_all("Website Item", fields=["name", "item_code", "enable_item_booking"]):
		if item.enable_item_booking:
			doc = frappe.get_doc("Item", item.item_code)
			website_item = frappe.get_doc("Website Item", item.name)

			for uom in doc.get("uoms"):
				website_item.append("enabled_booking_uom", {"uom": uom.uom})

			website_item.save()
