# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe import _
from frappe.email.inbox import link_communication_to_document
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder import DocType, Interval
from frappe.query_builder.functions import Now
from frappe.utils import cint, flt, get_fullname

from erpnext.crm.utils import add_link_in_communication, copy_comments
from erpnext.setup.utils import get_exchange_rate
from erpnext.utilities.transaction_base import TransactionBase


class Opportunity(TransactionBase):
	def after_insert(self):
		if self.opportunity_from == "Lead":
			frappe.get_doc("Lead", self.party_name).set_status(update=True)

		if self.opportunity_from in ["Lead", "Prospect"]:
			if frappe.db.get_single_value("CRM Settings", "carry_forward_communication_and_comments"):
				copy_comments(self.opportunity_from, self.party_name, self)
				add_link_in_communication(self.opportunity_from, self.party_name, self)

	def validate(self):
		self._prev = frappe._dict(
			{
				"contact_date": frappe.db.get_value("Opportunity", self.name, "contact_date")
				if (not cint(self.get("__islocal")))
				else None,
				"contact_by": frappe.db.get_value("Opportunity", self.name, "contact_by")
				if (not cint(self.get("__islocal")))
				else None,
			}
		)

		self.make_new_lead_if_required()
		self.validate_item_details()
		self.validate_uom_is_integer("uom", "qty")
		self.validate_cust_name()
		self.map_fields()

		if not self.title:
			self.title = self.customer_name

		if not self.with_items:
			self.items = []

		else:
			self.calculate_totals()

	def map_fields(self):
		for field in self.meta.get_valid_columns():
			if not self.get(field) and frappe.db.field_exists(self.opportunity_from, field):
				try:
					value = frappe.db.get_value(self.opportunity_from, self.party_name, field)
					frappe.db.set(self, field, value)
				except Exception:
					continue

	def calculate_totals(self):
		total = base_total = 0
		for item in self.get("items"):
			item.amount = flt(item.rate) * flt(item.qty)
			item.base_rate = flt(self.conversion_rate) * flt(item.rate)
			item.base_amount = flt(self.conversion_rate) * flt(item.amount)
			total += item.amount
			base_total += item.base_amount

		self.total = flt(total)
		self.base_total = flt(base_total)

	def make_new_lead_if_required(self):
		"""Set lead against new opportunity"""
		if (not self.get("party_name")) and self.contact_email:
			# check if customer is already created agains the self.contact_email
			dynamic_link, contact = DocType("Dynamic Link"), DocType("Contact")
			customer = (
				frappe.qb.from_(dynamic_link)
				.join(contact)
				.on(
					(contact.name == dynamic_link.parent)
					& (dynamic_link.link_doctype == "Customer")
					& (contact.email_id == self.contact_email)
				)
				.select(dynamic_link.link_name)
				.distinct()
				.run(as_dict=True)
			)

			if customer and customer[0].link_name:
				self.party_name = customer[0].link_name
				self.opportunity_from = "Customer"
				return

			lead_name = frappe.db.get_value("Lead", {"email_id": self.contact_email})
			if not lead_name:
				sender_name = get_fullname(self.contact_email)
				if sender_name == self.contact_email:
					sender_name = None

				if not sender_name and ("@" in self.contact_email):
					email_name = self.contact_email.split("@")[0]

					email_split = email_name.split(".")
					sender_name = ""
					for s in email_split:
						sender_name += s.capitalize() + " "

				lead = frappe.get_doc(
					{"doctype": "Lead", "email_id": self.contact_email, "lead_name": sender_name or "Unknown"}
				)

				lead.flags.ignore_email_validation = True
				lead.insert(ignore_permissions=True)
				lead_name = lead.name

			self.opportunity_from = "Lead"
			self.party_name = lead_name

	@frappe.whitelist()
	def declare_enquiry_lost(self, lost_reasons_list, competitors=None, detailed_reason=None):
		if not self.has_active_quotation():
			self.status = "Lost"
			self.lost_reasons = []
			self.competitors = []

			if detailed_reason:
				self.order_lost_reason = detailed_reason

			for reason in lost_reasons_list:
				self.append("lost_reasons", reason)

			for competitor in competitors or []:
				self.append("competitors", competitor)

			self.save()

		else:
			frappe.throw(_("Cannot declare as lost, because Quotation has been made."))

	def has_active_quotation(self):
		output = frappe.get_all(
			"Quotation",
			{"opportunity": self.name, "status": ("not in", ["Lost", "Closed"]), "docstatus": 1},
			"name",
		)
		if not output:
			output = frappe.db.sql(
				"""
				select q.name
				from `tabQuotation` q, `tabQuotation Item` qi
				where q.name = qi.parent and q.docstatus=1 and qi.prevdoc_docname =%s
				and q.status not in ('Lost', 'Closed')""",
				self.name,
			)

		return output

	def has_ordered_quotation(self):
		if not self.with_items:
			return frappe.get_all(
				"Quotation", {"opportunity": self.name, "status": "Ordered", "docstatus": 1}, "name"
			)
		else:
			return frappe.db.sql(
				"""
				select q.name
				from `tabQuotation` q, `tabQuotation Item` qi
				where q.name = qi.parent and q.docstatus=1 and qi.prevdoc_docname =%s
				and q.status = 'Ordered'""",
				self.name,
			)

	def has_lost_quotation(self):
		lost_quotation = frappe.db.sql(
			"""
			select name
			from `tabQuotation`
			where docstatus=1
				and opportunity =%s and status = 'Lost'
			""",
			self.name,
		)
		if lost_quotation:
			if self.has_active_quotation():
				return False
			return True

	def validate_cust_name(self):
		if self.party_name and self.opportunity_from == "Customer":
			self.customer_name = frappe.db.get_value("Customer", self.party_name, "customer_name")
		elif self.party_name and self.opportunity_from == "Lead":
			lead_name, company_name = frappe.db.get_value(
				"Lead", self.party_name, ["lead_name", "company_name"]
			)
			self.customer_name = company_name or lead_name

	def on_update(self):
		self.add_calendar_event()

	def add_calendar_event(self, opts=None, force=False):
		if frappe.db.get_single_value("CRM Settings", "create_event_on_next_contact_date_opportunity"):
			if not opts:
				opts = frappe._dict()

			opts.description = ""
			opts.contact_date = self.contact_date

			if self.party_name and self.opportunity_from == "Customer":
				if self.contact_person:
					opts.description = _("Contact {0}").format(self.contact_person)
				else:
					opts.description = _("Contact customer {0}").format(self.party_name)
			elif self.party_name and self.opportunity_from == "Lead":
				if self.contact_display:
					opts.description = _("Contact lead {0}").format(self.party_name)
				else:
					opts.description = _("Contact lead {0}").format(self.party_name)

			opts.subject = opts.description
			opts.description += _(". By : {0}").format(self.contact_by)

			if self.to_discuss:
				opts.description += _(" To Discuss : {0}").format(
					frappe.render_template(self.to_discuss, {"doc": self})
				)

			super(Opportunity, self).add_calendar_event(opts, force)

	def validate_item_details(self):
		if not self.get("items"):
			return

		# set missing values
		item_fields = ("item_name", "description", "item_group", "brand")

		for d in self.items:
			if not d.item_code:
				continue

			item = frappe.db.get_value("Item", d.item_code, item_fields, as_dict=True)
			for key in item_fields:
				if not d.get(key):
					d.set(key, item.get(key))


@frappe.whitelist()
def get_item_details(item_code, qty=0, customer=None, uom=None):
	from erpnext.accounts.party import get_default_price_list
	from erpnext.stock.get_item_details import get_conversion_factor, get_price_list_rate_for

	default_price_list = None
	if customer:
		default_price_list = get_default_price_list(frappe.get_doc("Customer", customer))
	if not default_price_list:
		default_price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")

	item = frappe.db.sql(
		"""select item_name, stock_uom, image, description, item_group, brand
		from `tabItem` where name = %s""",
		item_code,
		as_dict=1,
	)

	return {
		"item_name": item and item[0]["item_name"] or "",
		"uom": uom or (item and item[0]["stock_uom"]) or "",
		"description": item and item[0]["description"] or "",
		"image": item and item[0]["image"] or "",
		"item_group": item and item[0]["item_group"] or "",
		"brand": item and item[0]["brand"] or "",
		"price": item
		and get_price_list_rate_for(
			args={
				"price_list": default_price_list,
				"uom": uom or (item and item[0]["stock_uom"]),
				"ignore_party": not customer,
				"qty": qty,
				"conversion_factor": get_conversion_factor(item_code, uom).get("conversion_factor"),
			},
			item_code=item_code,
		),
	}


@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	def set_missing_values(source, target):
		from erpnext.controllers.accounts_controller import get_default_taxes_and_charges

		quotation = frappe.get_doc(target)

		company_currency = frappe.get_cached_value("Company", quotation.company, "default_currency")

		if company_currency == quotation.currency:
			exchange_rate = 1
		else:
			exchange_rate = get_exchange_rate(
				quotation.currency, company_currency, quotation.transaction_date, args="for_selling"
			)

		quotation.conversion_rate = exchange_rate

		# get default taxes
		taxes = get_default_taxes_and_charges(
			"Sales Taxes and Charges Template", company=quotation.company
		)
		if taxes.get("taxes"):
			quotation.update(taxes)

		quotation.run_method("set_missing_values")
		quotation.run_method("calculate_taxes_and_totals")
		if not source.with_items:
			quotation.opportunity = source.name

	doclist = get_mapped_doc(
		"Opportunity",
		source_name,
		{
			"Opportunity": {
				"doctype": "Quotation",
				"field_map": {"opportunity_from": "quotation_to", "name": "enq_no"},
			},
			"Opportunity Item": {
				"doctype": "Quotation Item",
				"field_map": {
					"parent": "prevdoc_docname",
					"parenttype": "prevdoc_doctype",
					"uom": "stock_uom",
				},
				"add_if_empty": True,
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist


@frappe.whitelist()
def make_request_for_quotation(source_name, target_doc=None):
	def update_item(obj, target, source_parent):
		target.conversion_factor = 1.0

	doclist = get_mapped_doc(
		"Opportunity",
		source_name,
		{
			"Opportunity": {"doctype": "Request for Quotation"},
			"Opportunity Item": {
				"doctype": "Request for Quotation Item",
				"field_map": [["name", "opportunity_item"], ["parent", "opportunity"], ["uom", "uom"]],
				"postprocess": update_item,
			},
		},
		target_doc,
	)

	return doclist


@frappe.whitelist()
def make_customer(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.opportunity_name = source.name

		if source.opportunity_from == "Lead":
			target.lead_name = source.party_name

	doclist = get_mapped_doc(
		"Opportunity",
		source_name,
		{
			"Opportunity": {
				"doctype": "Customer",
				"field_map": {"currency": "default_currency", "customer_name": "customer_name"},
			}
		},
		target_doc,
		set_missing_values,
	)

	return doclist


@frappe.whitelist()
def make_supplier_quotation(source_name, target_doc=None):
	doclist = get_mapped_doc(
		"Opportunity",
		source_name,
		{
			"Opportunity": {"doctype": "Supplier Quotation", "field_map": {"name": "opportunity"}},
			"Opportunity Item": {"doctype": "Supplier Quotation Item", "field_map": {"uom": "stock_uom"}},
		},
		target_doc,
	)

	return doclist


@frappe.whitelist()
def set_multiple_status(names, status):
	names = json.loads(names)
	for name in names:
		opp = frappe.get_doc("Opportunity", name)
		opp.status = status
		opp.save()


def auto_close_opportunity():
	"""auto close the `Replied` Opportunities after 7 days"""
	auto_close_after_days = (
		frappe.db.get_single_value("CRM Settings", "close_opportunity_after_days") or 15
	)

	table = frappe.qb.DocType("Opportunity")
	opportunities = (
		frappe.qb.from_(table)
		.select(table.name)
		.where(
			(table.modified < (Now() - Interval(days=auto_close_after_days))) & (table.status == "Replied")
		)
	).run(pluck=True)

	for opportunity in opportunities:
		doc = frappe.get_doc("Opportunity", opportunity)
		doc.status = "Closed"
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.save()


@frappe.whitelist()
def make_opportunity_from_communication(communication, company, ignore_communication_links=False):
	from erpnext.crm.doctype.lead.lead import make_lead_from_communication

	doc = frappe.get_doc("Communication", communication)

	lead = doc.reference_name if doc.reference_doctype == "Lead" else None
	if not lead:
		lead = make_lead_from_communication(communication, ignore_communication_links=True)

	opportunity_from = "Lead"

	opportunity = frappe.get_doc(
		{
			"doctype": "Opportunity",
			"company": company,
			"opportunity_from": opportunity_from,
			"party_name": lead,
		}
	).insert(ignore_permissions=True)

	link_communication_to_document(doc, "Opportunity", opportunity.name, ignore_communication_links)

	return opportunity.name


@frappe.whitelist()
def get_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.
	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	from frappe.desk.calendar import get_event_conditions

	conditions = get_event_conditions("Opportunity", filters)

	data = frappe.db.sql(
		"""
		select
			distinct `tabOpportunity`.name, `tabOpportunity`.customer_name, `tabOpportunity`.opportunity_amount,
			`tabOpportunity`.title, `tabOpportunity`.contact_date
		from
			`tabOpportunity`
		where
			(`tabOpportunity`.contact_date between %(start)s and %(end)s)
			{conditions}
		""".format(
			conditions=conditions
		),
		{"start": start, "end": end},
		as_dict=True,
		update={"allDay": 0},
	)
	return data
