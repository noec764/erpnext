import frappe
from frappe.utils import cint


def execute():
	if not frappe.get_all("Item", filters={"enable_item_booking": 1}):
		return

	venue_settings = frappe.get_single("Venue Settings")
	if venue_settings.venue_units_of_measure:
		return

	# Don't add UOM below one hour
	uoms = frappe.get_all(
		"UOM Conversion Factor",
		filters={"to_uom": venue_settings.minute_uom, "value": (">", 60)},
		fields=["from_uom", "value"],
	)
	for uom in uoms:
		venue_settings.append(
			"venue_units_of_measure", {"unit_of_measure": uom.from_uom, "duration": cint(uom.value) * 60}
		)

	venue_settings.save()
