# Copyright (c) 2022, Dokos SAS and Contributors
# License: See license.txt

import math
from typing import Optional

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, formatdate, getdate

from erpnext.hr.utils import (
	EarnedLeaveAllocator,
	EarnedLeaveCalculator,
	create_additional_leave_ledger_entry,
	get_holidays_for_employee,
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

		if getdate(self.parent.today) >= getdate(
			frappe.db.get_value("Leave Period", allocation.leave_period, "to_date")
		):
			new_allocation = math.ceil(flt(new_allocation))

		allocation_difference = flt(new_allocation) - flt(allocation.total_leaves_allocated)

		allocation.db_set("total_leaves_allocated", new_allocation, update_modified=False)
		create_additional_leave_ledger_entry(allocation, allocation_difference, self.parent.today)

		text = _("allocated {0} leave(s) via scheduler on {1}").format(
			frappe.bold(self.earned_leaves), frappe.bold(formatdate(self.parent.today))
		)

		allocation.add_comment(comment_type="Info", text=text)


def get_regional_number_of_leave_days(
	employee: str,
	leave_type: str,
	from_date: str,
	to_date: str,
	half_day: Optional[int] = None,
	half_day_date: Optional[str] = None,
	holiday_list: Optional[str] = None,
) -> float:
	"""Returns number of leave days between 2 dates after considering half day and holidays
	(Based on the include_holiday setting in Leave Type)"""
	holidays = [d.holiday_date for d in get_holidays_for_employee(employee, from_date, to_date)]
	next_expected_working_day = add_days(getdate(from_date), 1)
	while next_expected_working_day in holidays:
		next_expected_working_day = add_days(getdate(next_expected_working_day), 1)

	number_of_days = 0
	if cint(half_day) == 1:
		if getdate(from_date) == getdate(to_date):
			number_of_days = 0.5
		elif half_day_date and getdate(next_expected_working_day) <= getdate(half_day_date) <= getdate(
			to_date
		):
			number_of_days = date_diff(to_date, next_expected_working_day) + 0.5
		else:
			number_of_days = date_diff(to_date, next_expected_working_day)
	else:
		number_of_days = date_diff(to_date, next_expected_working_day)

	leave_type = frappe.db.get_value(
		"Leave Type",
		leave_type,
		[
			"include_holiday",
			"is_earned_leave",
			"earned_leave_frequency",
			"earned_leave_frequency_formula",
		],
		as_dict=True,
	)

	if leave_type.is_earned_leave and leave_type.earned_leave_frequency == "Custom Formula":
		if leave_type.earned_leave_frequency_formula == "Congés payés sur jours ouvrables":
			# TODO: Appliquer la règle des 5 samedis maximum
			non_weekly_holidays = [
				d.holiday_date
				for d in get_holidays_for_employee(employee, from_date, to_date, only_non_weekly=True)
			]
			holidays = [d for d in holidays if d.day != 6 and d not in non_weekly_holidays]

	if not leave_type.include_holiday:
		number_of_days = flt(number_of_days) - flt(holidays)

	return number_of_days
