from datetime import timedelta
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cstr, getdate, nowdate, time_diff_in_hours, flt

@frappe.whitelist()
def get_resources(company, start, end, group_by=None):
	employees = frappe.get_all("Employee",
			filters={"status": "Active", "company": company},
			fields=["name", "employee_name", "department", "company", "user_id"])

	employee_list = [x.name for x in employees]
	working_time = {
		x.employee: x.weekly_working_hours for x in
		frappe.get_all("Employment Contract",
			filters={
				"employee": ("in", employee_list),
				"start_date": ("<=", nowdate()),
				"ifnull(end_date, '3999-12-31')": (">=", nowdate())
			},
			fields=["employee", "weekly_working_hours"])
	}

	groups = defaultdict(set)
	if group_by == "department":
		shift_group_by = {x.name: x[group_by] for x in frappe.get_all("Shift Type", fields=["name", group_by], distinct=True)}

		for ass in get_assignments(start, end, return_records=True):
			group_by_data = shift_group_by.get(ass.get("shift_type"))
			groups[group_by_data].add(ass.get("employee"))

	resources = []
	for e in employees:
		resource = {
			"id": e.name,
			"title": e.employee_name,
			"department": e.department,
			"company": e.company,
			"user_id": e.user_id,
			"working_time": working_time.get(e.name),
			"total": None
		}

		if group_by and groups:
			for group in groups:
				if e.name in groups[group]:
					new_resource = resource.copy()
					# new_resource.update({"id": f"{e.name}_{group}"})
					new_resource.update({group_by: group})
					resources.append(new_resource)
				else:
					resources.append(resource)
		else:
			resources.append(resource)

	return resources

@frappe.whitelist()
def get_resources_total(start, end):
	assignments = get_assignments(start, end)

	total = defaultdict(float)
	for a in assignments:
		total[a.get("resourceId")] += flt(a.get("duration"))

	return total

@frappe.whitelist()
def get_shift_types():
	return [
		{
			"name": st.name,
			"startTime": st.start_time,
			"duration": time_diff_in_hours(st.end_time, st.start_time)
		}
		for st in frappe.get_all("Shift Type",
			fields=["name", "start_time", "end_time"]
		)
	]

@frappe.whitelist()
def get_events(start, end, filters=None):
	if filters:
		filters = frappe.parse_json(filters)

	out = get_holidays(start, end, filters)
	out.extend(get_leave_applications(start, end, filters))
	out.extend(get_trainings(start, end, filters))
	out.extend(get_assignments(start, end, filters))
	return out

def get_holidays(start_date, end_date, filters=None):
	query_filters = {"status": "Active"}
	if filters:
		query_filters.update(filters)

	employees = frappe.get_all("Employee",
		filters=query_filters,
		pluck="name")

	holidays = []
	for employee in employees:
		holidays_for_employee = get_holidays_for_employee(employee, start_date, end_date)

		for hle in holidays_for_employee:
			holidays.append({
				"id": hle.name,
				"resourceId": employee,
				"start": hle.holiday_date,
				"end": hle.holiday_date,
				"title": hle.description,
				"editable": 0,
				"display": "background",
				"backgroundColor": "var(--green-300)",
				"doctype": "Holiday List"
			})

	return holidays

def get_holidays_for_employee(employee, start_date, end_date):
	from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee
	holiday_list = get_holiday_list_for_employee(employee)

	def linked_holiday_lists(hl):
		former_hl = hl
		while former_hl is not None:
			former_hl = frappe.db.get_value("Holiday List", hl, "replaces_holiday_list")
			if former_hl:
				hl = former_hl
				yield former_hl

	linked_holiday_lists = list(linked_holiday_lists(holiday_list))
	total_holidays = [holiday_list] + linked_holiday_lists

	holidays = frappe.db.sql('''select name, holiday_date, description from `tabHoliday`
		where
			parent in %(holiday_list)s
			and holiday_date >= %(start_date)s
			and holiday_date <= %(end_date)s''', {
				"holiday_list": tuple(total_holidays),
				"start_date": start_date,
				"end_date": end_date
			}, as_dict=True)

	return holidays

def get_leave_applications(start, end, filters=None):
	query_filters = {"status": "Approved"}
	if filters:
		query_filters.update(filters)

	return [
		{
			"id": l.name,
			"resourceId": l.employee,
			"start": l.from_date,
			"end": l.to_date,
			"title": l.leave_type,
			"editable": 0,
			"display": "background",
			"backgroundColor": "var(--green-300)",
			"doctype": "Leave Application"
		}
		for l in frappe.get_all("Leave Application",
			filters=query_filters,
			fields=["name", "leave_type", "employee", "from_date", "to_date"]
		)
	]

def get_assignments(start, end, filters=None, conditions=None, return_records=False):
	from frappe.desk.reportview import get_filters_cond
	events = []
	query = """select name, start_date, end_date, employee_name,
		employee, docstatus, shift_type
		from `tabShift Assignment` where
		(start_date >= %(start_date)s
		or (end_date <=  %(end_date)s and end_date >=  %(end_date)s)
		or (%(start_date)s between start_date and end_date and %(end_date)s between start_date and end_date))
		"""
	if conditions:
		query += conditions

	if filters:
		query += get_filters_cond("Shift Assignment", filters, [])

	records = frappe.db.sql(query, {"start_date":start, "end_date":end}, as_dict=True)

	if return_records:
		return records

	shift_type_data = {}
	for d in records:
		if d.shift_type not in shift_type_data:
			shift_type_data[d.shift_type] = frappe.db.get_value("Shift Type", d.shift_type, ["start_time", "end_time"])

		daily_event_start = d.start_date
		daily_event_end = d.end_date if d.end_date else getdate()
		delta = timedelta(days=1)
		while daily_event_start <= daily_event_end:
			e = {
				"id": d.name,
				"resourceId": d.employee,
				"doctype": "Shift Assignment",
				"start": daily_event_start,
				"end": daily_event_end,
				"title": cstr(d.shift_type),
				"editable": d.docstatus == 0,
				"color": "var(--gray-500)" if d.docstatus == 0 else "var(--blue-500)",
				"duration": time_diff_in_hours(shift_type_data.get(d.shift_type)[1], shift_type_data.get(d.shift_type)[0])
			}
			if e not in events:
				events.append(e)

			daily_event_start += delta

	return events

def get_trainings(start, end, filters=None):
	query_filters = {
		"start_time": (">=", getdate(start)),
		"end_time": ("<=", getdate(end)),
	}
	if filters:
		query_filters.update(filters)

	return [
		{
			"id": e.name,
			"resourceId": e.employee,
			"start": e.start_time,
			"end": e.end_time,
			"title": e.event_name,
			"editable": 0,
			"display": "background",
			"backgroundColor": "var(--red-300)",
			"doctype": "Training Event"
		}
		for e in frappe.get_all(
			"Training Event",
			filters=query_filters,
			fields=["name", "`tabTraining Event Employee`.employee", "start_time", "end_time", "event_name"]
		)
	]
