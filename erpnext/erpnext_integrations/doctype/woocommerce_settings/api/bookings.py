from erpnext.erpnext_integrations.doctype.woocommerce_settings.api import WooCommerceAPI


class WooCommerceBookings(WooCommerceAPI):
	def __init__(self, version="wc-bookings/v1", *args, **kwargs):
		super(WooCommerceBookings, self).__init__(version, args, kwargs)

	def get_booking(self, id, params=None):
		return self.get(f"bookings/{id}", params=params)

	def get_bookings(self, params=None):
		return self.get("bookings", params=params)
