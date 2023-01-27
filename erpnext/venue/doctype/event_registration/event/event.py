# Copyright (c) 2021, Dokos SAS and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from frappe.desk.doctype.event.event import Event


class EventIsFull(frappe.ValidationError):
	@classmethod
	def throw(cls):
		frappe.throw(_("This event is fully booked."), cls)


class EventIsOverbooked(frappe.ValidationError):
	@classmethod
	def throw(cls):
		frappe.throw(_("This event is overbooked."), cls)

	@classmethod
	def throw_desk(cls):
		frappe.throw(_("This event is overbooked. Either increase the number of maximum registrations, or cancel some registrations."), cls)


class DokosEvent(Event):
	def validate(self):
		super().validate()
		self.validate_remaining_capacity()

	def validate_remaining_capacity(self):
		capacity_info = get_capacity_info(self)
		if capacity_info["allow_registrations"] and capacity_info["overbooking"]:
			EventIsOverbooked.throw_desk()

	def get_context(self, context):
		# no_cache show_sidebar show_close_button content event_style attachments
		super().get_context(context)

		context.template = "/venue/doctype/event_registration/event/templates/event.html"

		fields = []
		for field in frappe.get_meta("Event Registration").fields:
			if not (field.fieldname == "amended_from" or field.permlevel > 0):
				field.label = _(field.label)
				fields.append(field)

		context.registration_form = frappe.as_json(fields)

		if frappe.session.user != "Guest":
			context.is_registered = frappe.db.exists(
				"Event Registration", dict(user=frappe.session.user, event=self.name, docstatus=1)
			)
			context.my_registrations = frappe.get_list(
				"Event Registration",
				fields=["name", "docstatus", "first_name", "last_name"],
				filters=dict(user=frappe.session.user, event=self.name),
			)

		context.event_capacity_info = get_capacity_info(self)

		if self.registration_web_form:
			web_form_route = frappe.get_value("Web Form", self.registration_web_form, "route")
			context.registration_url = f"/{web_form_route}/new?event={self.name}"

		context.can_edit_event = self.has_permission("write")



from typing import TypedDict, Literal
class CapacityInfo(TypedDict):
	allow_registrations: bool
	is_full: bool
	has_limit: bool
	current: int
	overbooking: int
	free: int | Literal["Infinity"]  # "Infinity" as a string because of JSON parsing
	limit: int | Literal["Infinity"]


@frappe.whitelist()
def get_capacity_info(event: str) -> CapacityInfo:
	from pypika import functions as fn

	fields = ["name", "published", "allow_registrations", "max_number_of_registrations"]
	if isinstance(event, Event):
		event_info = { k: event.get(k) for k in fields }
	elif isinstance(event, str):
		event_info = frappe.db.get_value("Event", event, fields, as_dict=True)
	else:
		raise frappe.exceptions.InvalidNameError(repr(event))

	allow_registrations = bool(event_info["allow_registrations"] and event_info["published"])
	max_number_of_registrations = int(event_info["max_number_of_registrations"] or 0)

	ER = frappe.qb.DocType("Event Registration")
	query = (
		frappe.qb.select(fn.Count(ER.star))
		.from_(ER)
		.where(ER.event == event_info["name"])
		.where(ER.docstatus == 1)
	)
	count = int(query.run()[0][0])
	infinity = "Infinity"

	if max_number_of_registrations == 0:  # no limit
		free = infinity
		overbooking = 0
	elif count <= max_number_of_registrations:  # normal
		free = max_number_of_registrations - count
		overbooking = 0
	else:  # overbooked
		free = 0
		overbooking = count - max_number_of_registrations

	return {
		"allow_registrations": allow_registrations,
		"current": count,
		"free": free,
		"overbooking": overbooking,
		"is_full": free == 0,
		"has_limit": max_number_of_registrations > 0,
		"limit": max_number_of_registrations or infinity,
	}


# def get_list_context(context=None):
# 	context.update(
# 		{
# 			"title": _("Upcoming Events"),
# 			"no_cache": 1,
# 			"no_breadcrumbs": True,
# 			"show_sidebar": frappe.session.user != "Guest",
# 			"get_list": get_events_list,
# 			"row_template": "desk/doctype/event/templates/event_row.html",
# 			"header_action": frappe.render_template(
# 				"desk/doctype/event/templates/event_list_action.html", {}
# 			),
# 			"base_scripts": ["events-portal.bundle.js", "controls.bundle.js"],
# 		}
# 	)
