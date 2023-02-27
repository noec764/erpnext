import "frappe/public/js/frappe/ui/floating_button/back_button";

frappe.back_button_specs["booking-search"] = {
	label: __("Back to Search"),
	icon: "search",
}
const back_button = new frappe.ui.BackButton()

import "./calendar_pages/booking_section"
import "./calendar_pages/event_slots_calendar.js"
import "./calendar_pages/item_booking_calendar.js"
