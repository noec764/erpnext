import frappe


def execute():
	frappe.reload_doc("venue", "doctype", "Venue Settings")

	stock_settings = frappe.get_single("Stock Settings")
	venue_settings = frappe.get_single("Venue Settings")
	for field in ["minute_uom", "clear_item_booking_draft_duration", "enable_simultaneous_booking", "sync_with_google_calendar"]:
		if getattr(stock_settings, field):
			setattr(venue_settings, field, getattr(stock_settings, field, None))