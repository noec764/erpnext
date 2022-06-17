# Copyright (c) 2020, Dokos SAS and Contributors
# License: See license.txt

import math

import frappe
from frappe import _
from frappe.utils import flt, formatdate, getdate, today

from erpnext.hr.utils import (
	EarnedLeaveAllocator,
	EarnedLeaveCalculator,
	create_additional_leave_ledger_entry,
)


def allocate_earned_leaves():
	FranceLeaveAllocator(FranceLeaveCalculator).allocate()


class FranceLeaveAllocator(EarnedLeaveAllocator):
	def __init__(self, calculator, date=None):
		super(FranceLeaveAllocator, self).__init__(calculator, date)


class FranceLeaveCalculator(EarnedLeaveCalculator):
	def __init__(self, parent, leave_type, allocation):
		super(FranceLeaveCalculator, self).__init__(parent, leave_type, allocation)
		self.formula_map = {
			"Congés payés sur jours ouvrables": self.conges_payes_ouvrables,
			"Congés payés sur jours ouvrés": self.conges_payes_ouvres,
		}

	def conges_payes_ouvrables(self):
		self.earned_leaves = self.earneable_leaves * flt(
			max(
				round(len(self.attendance.get("dates", [])) / 24), round(self.attendance.get("weeks", 0) / 4)
			)
		)
		self.allocate_earned_leaves_based_on_formula()

	def conges_payes_ouvres(self):
		self.earned_leaves = self.earneable_leaves * flt(
			max(
				round(len(self.attendance.get("dates", [])) / 20), round(self.attendance.get("weeks", 0) / 4)
			)
		)
		self.allocate_earned_leaves_based_on_formula()

	def allocate_earned_leaves_based_on_formula(self):
		allocation = frappe.get_doc("Leave Allocation", self.allocation.name)
		new_allocation = flt(allocation.new_leaves_allocated) + flt(self.earned_leaves)

		if (
			new_allocation > self.leave_type.max_leaves_allowed and self.leave_type.max_leaves_allowed > 0
		):
			new_allocation = self.leave_type.max_leaves_allowed

		if new_allocation == allocation.total_leaves_allocated:
			return

		if getdate(today()) >= getdate(
			frappe.db.get_value("Leave Period", allocation.leave_period, "to_date")
		):
			new_allocation = math.ceil(flt(new_allocation))

		allocation_difference = flt(new_allocation) - flt(allocation.total_leaves_allocated)

		allocation.db_set("total_leaves_allocated", new_allocation, update_modified=False)
		create_additional_leave_ledger_entry(allocation, allocation_difference, self.parent.today)

		text = _("allocated {0} leave(s) via scheduler on {1}").format(
			frappe.bold(self.earned_leaves), frappe.bold(formatdate(today()))
		)

		allocation.add_comment(comment_type="Info", text=text)
