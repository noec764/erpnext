# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

# For license information, please see license.txt


from typing import Literal

import frappe
from frappe import _, msgprint, throw
from frappe.model.document import Document
from frappe.utils import cstr, flt, fmt_money, getdate

import erpnext


class OverlappingConditionError(frappe.ValidationError):
	pass


class FromGreaterThanToError(frappe.ValidationError):
	pass


class ManyBlankToValuesError(frappe.ValidationError):
	pass


NOT_APPLICABLE = "not applicable"

SALES_DOCTYPES = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice", "POS Invoice"]


class ShippingRule(Document):
	label: str
	shipping_rule_type: Literal["Selling", "Buying"]
	calculate_based_on: Literal["Fixed", "Net Total", "Net Weight", "Custom Formula"]
	shipping_amount: float
	conditions: list
	countries: list
	custom_formula: str

	def validate(self):
		if self.shipping_rule_type != "Selling":
			# Taxes are not yet implemented for purchasing documents
			self.shipping_taxes = []

		if self.calculate_based_on not in ["Fixed", "Custom Formula"]:
			self.validate_from_to_values()
			self.sort_shipping_rule_conditions()
			self.validate_overlapping_shipping_rule_conditions()
		if self.calculate_based_on == "Custom Formula":
			if not self.custom_formula:
				raise frappe.MandatoryError(f'{self!r}: {_("Custom Formula")}')

	def validate_from_to_values(self):
		zero_to_values = []

		for d in self.get("conditions"):
			self.round_floats_in(d)

			# values cannot be negative
			self.validate_value("from_value", ">=", 0.0, d)
			self.validate_value("to_value", ">=", 0.0, d)

			if not d.to_value:
				zero_to_values.append(d)
			elif d.from_value >= d.to_value:
				throw(
					_("From value must be less than to value in row {0}").format(d.idx), FromGreaterThanToError
				)

		# check if more than two or more rows has To Value = 0
		if len(zero_to_values) >= 2:
			throw(
				_('There can only be one Shipping Rule Condition with 0 or blank value for "To Value"'),
				ManyBlankToValuesError,
			)

	def _evaluate_custom_formula(self, doc):
		shipping_amount = frappe.safe_eval(self.custom_formula, None, {"doc": doc.as_dict()})

		# from frappe.utils.safe_block_eval import safe_block_eval
		# loc = {"doc": doc.as_dict(), "shipping_amount": None}
		# shipping_amount = safe_block_eval(code, None, loc, output_var="shipping_amount")

		if shipping_amount == NOT_APPLICABLE:
			return NOT_APPLICABLE

		if not isinstance(shipping_amount, (int, float)):
			frappe.throw("Shipping Rule: Custom formula must return a number")

		return shipping_amount

	def _evaluate_from_hook(self, transaction: Document):
		shipping_amount = self.run_method("evaluate_shipping_rule", transaction=transaction)

		if shipping_amount == NOT_APPLICABLE:
			return NOT_APPLICABLE

		if not isinstance(shipping_amount, (int, float)):
			frappe.throw("Shipping Rule: Hook must return a number")

		return float(shipping_amount)

	def evaluate_shipping_rule(
		self, transaction: Document
	) -> None | float | Literal["not applicable"]:
		"""Hook to evaluate shipping amount"""
		return None

	def get_shipping_amount(self, doc: Document) -> float | Literal["not applicable"]:
		shipping_amount = 0.0

		if self.calculate_based_on == "Net Total":
			shipping_amount = self.get_shipping_amount_from_rules(doc.base_net_total)

		elif self.calculate_based_on == "Net Weight":
			shipping_amount = self.get_shipping_amount_from_rules(doc.total_net_weight)

		elif self.calculate_based_on == "Fixed":
			shipping_amount = self.shipping_amount

		elif self.calculate_based_on == "Custom Formula":
			shipping_amount = self._evaluate_custom_formula(doc)

		elif self.calculate_based_on == "Hook":
			shipping_amount = self._evaluate_from_hook(doc)

		# convert to order currency
		if doc.currency != doc.company_currency:
			shipping_amount = flt(shipping_amount / doc.conversion_rate, 2)

		return shipping_amount

	def apply(self, doc):
		"""Apply shipping rule on given doc. Called from accounts controller"""
		if doc.get_shipping_address():
			# validate country only if there is address
			self.validate_countries(doc)

		shipping_amount = self.get_shipping_amount(doc)

		if shipping_amount == "not applicable":
			frappe.throw(_("Shipping Rule is not applicable"))

		self.add_shipping_rule_to_tax_table(doc, shipping_amount)

	def get_shipping_amount_from_rules(self, value):
		for condition in self.get("conditions"):
			if not condition.to_value or (
				flt(condition.from_value) <= flt(value) <= flt(condition.to_value)
			):
				return flt(condition.shipping_amount)

		return 0.0  # NOTE: Should this be 0.0 or "not applicable"?

	def validate_countries(self, doc):
		# validate applicable countries
		if self.countries:
			shipping_country = doc.get_shipping_address().get("country")
			if not shipping_country:
				frappe.throw(
					_("Shipping Address does not have country, which is required for this Shipping Rule")
				)
			if shipping_country not in [d.country for d in self.countries]:
				frappe.throw(
					_("Shipping rule not applicable for country {0} in Shipping Address").format(shipping_country)
				)

	def add_shipping_rule_to_tax_table(self, doc, shipping_amount):
		shipping_charge = {
			"charge_type": "Actual",
			"account_head": self.account,
			"cost_center": self.cost_center,
		}
		if self.shipping_rule_type == "Selling":
			# check if not applied on purchase
			if not doc.meta.get_field("taxes").options == "Sales Taxes and Charges":
				frappe.throw(_("Shipping rule only applicable for Selling"))

			shipping_charge["doctype"] = "Sales Taxes and Charges"

		else:
			# check if not applied on sales
			if not doc.meta.get_field("taxes").options == "Purchase Taxes and Charges":
				frappe.throw(_("Shipping rule only applicable for Buying"))

			shipping_charge["doctype"] = "Purchase Taxes and Charges"
			shipping_charge["category"] = "Valuation and Total"
			shipping_charge["add_deduct_tax"] = "Add"

		# Find existing shipping charge row
		if matches := doc.get("taxes", filters=shipping_charge):
			# take the last record found
			shipping_charge_row = matches[-1]
		else:
			shipping_charge_row = doc.append("taxes", shipping_charge)

		# Update the found shipping charge or set the amount of the new one
		shipping_charge_row.update(
			{
				"tax_amount": shipping_amount,
				"description": self.label,
			}
		)

		# Add tax on shipping if applicable
		if self.shipping_rule_type == "Selling" and self.shipping_taxes:
			if tax_template := get_shipping_tax_template(doc, self.shipping_taxes):
				self.add_tax_on_shipping(
					doc,
					shipping_charge_row,
					tax_template_dt="Sales Taxes and Charges Template",
					tax_template_name=tax_template,
				)

	def add_tax_on_shipping(self, doc, shipping_charge_row, tax_template_dt, tax_template_name):
		# Find existing tax by referenced row id (the not-so-clearly named row_id)
		# NOTE: Do NOT use doc.get with filters, as the row_id is not an 'int' but a 'str'
		tax_on_shipping_row = None
		for tax in doc.get("taxes"):
			if str(tax.row_id) == str(shipping_charge_row.idx):
				tax_on_shipping_row = tax
				# keep last -> no break

		# If there is no tax on shipping, create it
		if not tax_on_shipping_row:
			tax_on_shipping_row = doc.append("taxes", {})

		from erpnext.controllers.accounts_controller import get_taxes_and_charges

		tax_template: list = get_taxes_and_charges(tax_template_dt, tax_template_name)

		if len(tax_template) != 1:
			frappe.throw(
				_("{0}: {1}").format(
					_("Shipping rule has invalid tax template"),
					_("Must have exactly one row"),
				)
			)

		tax_on_shipping_values = tax_template[0]
		accepted_charge_types = ["Actual", "On Previous Row Amount", "On Net Total"]
		if tax_on_shipping_values.charge_type not in accepted_charge_types:
			frappe.throw(
				_("{0}: {1}").format(
					_("Shipping rule has invalid tax template"),
					_("Charge type must be one of {0}").format(", ".join(accepted_charge_types)),
				)
			)

		# HACK: Transform "On Net Total" into "On Previous Row Amount"
		# because here we're only considering the shipping charge
		if tax_on_shipping_values.charge_type == "On Net Total":
			tax_on_shipping_values.charge_type = "On Previous Row Amount"

		# Update the tax on shipping row
		if tax_on_shipping_values.charge_type == "Actual":
			tax_on_shipping_values.row_id = None
		else:
			tax_on_shipping_values.row_id = shipping_charge_row.idx

		tax_on_shipping_values.description = (
			self.label + " - " + (tax_on_shipping_values.description or tax_template_name)
		)

		tax_on_shipping_row.update(tax_on_shipping_values)

	def sort_shipping_rule_conditions(self):
		"""Sort Shipping Rule Conditions based on increasing From Value"""
		self.shipping_rules_conditions = sorted(self.conditions, key=lambda d: flt(d.from_value))
		for i, d in enumerate(self.conditions):
			d.idx = i + 1

	def validate_overlapping_shipping_rule_conditions(self):
		def overlap_exists_between(num_range1, num_range2):
			"""
			num_range1 and num_range2 are two ranges
			ranges are represented as a tuple e.g. range 100 to 300 is represented as (100, 300)
			if condition num_range1 = 100 to 300
			then condition num_range2 can only be like 50 to 99 or 301 to 400
			hence, non-overlapping condition = (x1 <= x2 < y1 <= y2) or (y1 <= y2 < x1 <= x2)
			"""
			(x1, x2), (y1, y2) = num_range1, num_range2
			separate = (x1 <= x2 <= y1 <= y2) or (y1 <= y2 <= x1 <= x2)
			return not separate

		overlaps = []
		for i in range(0, len(self.conditions)):
			for j in range(i + 1, len(self.conditions)):
				d1, d2 = self.conditions[i], self.conditions[j]
				if d1.as_dict() != d2.as_dict():
					# in our case, to_value can be zero, hence pass the from_value if so
					range_a = (d1.from_value, d1.to_value or d1.from_value)
					range_b = (d2.from_value, d2.to_value or d2.from_value)
					if overlap_exists_between(range_a, range_b):
						overlaps.append([d1, d2])

		if overlaps:
			company_currency = erpnext.get_company_currency(self.company)
			msgprint(_("Overlapping conditions found between:"))
			messages = []
			for d1, d2 in overlaps:
				messages.append(
					"%s-%s = %s "
					% (d1.from_value, d1.to_value, fmt_money(d1.shipping_amount, currency=company_currency))
					+ _("and")
					+ " %s-%s = %s"
					% (d2.from_value, d2.to_value, fmt_money(d2.shipping_amount, currency=company_currency))
				)

			msgprint("\n".join(messages), raise_exception=OverlappingConditionError)


def get_ecommerce_shipping_rules(transaction: Document, address=None) -> list[ShippingRule]:
	address = address or transaction.get_shipping_address()  # type: ignore

	if not address:
		# Cannot filter by country if no address
		return []

	if isinstance(address, str):
		country = frappe.db.get_value("Address", address, "country")
	else:
		country = address.get("country")

	if not country:
		# The address has no country
		return []

	# First, get all shipping rules that apply to the country, and retrieve basic fields
	sr_country = frappe.qb.DocType("Shipping Rule Country")
	sr = frappe.qb.DocType("Shipping Rule")

	from pypika import Order

	query = (
		frappe.qb.from_(sr)
		.left_join(sr_country)
		.on(sr.name == sr_country.parent)
		.select(sr.name)
		.distinct()
		.where((sr_country.country == country) | sr_country.country.isnull())
		.where(sr.disabled != 1)
		.where(sr.show_on_website == 1)
		.orderby(sr.name, order=Order.asc)
	)
	shipping_rule_names = [x[0] for x in query.run(as_list=True)]

	shipping_rules: list[ShippingRule] = list(
		map(lambda name: frappe.get_doc("Shipping Rule", name), shipping_rule_names)
	)  # type: ignore

	# Filter out shipping rules that don't apply to the transaction
	shipping_rules = list(
		filter(lambda sr: sr.get_shipping_amount(transaction) != "not applicable", shipping_rules)
	)

	if not shipping_rules:
		# No shipping rules for this country
		return []

	return shipping_rules  # type: ignore


def get_shipping_tax_template(doc, taxes):
	taxes_with_validity = []
	taxes_with_no_validity = []

	for tax in taxes:
		tax_company = frappe.get_value("Sales Taxes and Charges Template", tax.tax_template, "company")

		if tax_company == doc.company:
			if tax.valid_from:
				validation_date = doc.get("transaction_date") or doc.get("posting_date")

				if getdate(tax.valid_from) <= getdate(validation_date):
					taxes_with_validity.append(tax)
			else:
				taxes_with_no_validity.append(tax)

	if taxes_with_validity:
		taxes = (
			sorted(taxes_with_validity, key=lambda i: i.valid_from, reverse=True) + taxes_with_no_validity
		)
	else:
		taxes = taxes_with_no_validity

	# all templates have validity and no template is valid
	if not taxes_with_validity and (not taxes_with_no_validity):
		return None

	for tax in taxes:
		if cstr(tax.tax_category) == cstr(doc.get("tax_category")):
			return tax.tax_template

	return None
