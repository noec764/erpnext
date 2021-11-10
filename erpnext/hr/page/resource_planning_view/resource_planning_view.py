from datetime import timedelta
from collections import defaultdict

import frappe
from frappe import _
from frappe.desk.form.assign_to import add
from frappe.utils import cstr, getdate, nowdate, time_diff_in_hours, flt, format_time, date_diff, add_days, format_date

@frappe.whitelist()
def get_resources(company, start, end, employee=None, department=None, group_by=None, with_tasks=False):
	query_filters = {"status": "Active", "company": company}

	if department:
		query_filters.update({"department": department})

	if employee:
		query_filters.update({"name": employee})

	employees = frappe.get_all("Employee",
			filters=query_filters,
			fields=["name", "employee_name", "department", "company", "user_id"])

	employee_list = {x.name: [x.company, x.user_id, x.employee_name] for x in employees}
	number_of_weeks = (getdate(end).isocalendar()[1] - getdate(start).isocalendar()[1]) + 1
	working_time = {
		x.employee: x.weekly_working_hours for x in
		frappe.get_all("Employment Contract",
			filters={
				"employee": ("in", employee_list.keys()),
				"date_of_joining": ("<=", nowdate()),
				"ifnull(relieving_date, '3999-12-31')": (">=", nowdate())
			},
			fields=["employee", "weekly_working_hours"])
	}

	if group_by:
		query_filters = {"projects": []}
		if employee:
			query_filters.update({"employee": employee})
		if department:
			query_filters.update({"department": department})

		events = get_events(start, end, query_filters, with_tasks=with_tasks)

		groups = defaultdict(set)
		for event in events:
			emp = event.get("employee") or event.get("resourceId")
			group_by_data = event.get(group_by.lower())
			if group_by_data:
				groups[group_by_data].add(emp)

	resources = []
	if group_by and groups:
		for group in groups:
			for employee in groups[group]:
				resources.append({
					"id": f"{employee}_{group}",
					"title": employee_list.get(employee)[2],
					group_by.lower(): group,
					"company": employee_list.get(employee)[0],
					"user_id": employee_list.get(employee)[1],
					"working_time": flt(working_time.get(employee)) * flt(number_of_weeks),
					"employee_id": employee,
					"total": None
				})
	else:
		for e in employees:
			resources.append({
				"id": e.name,
				"title": e.employee_name,
				"department": e.department,
				"company": e.company,
				"user_id": e.user_id,
				"working_time": flt(working_time.get(e.name)) * flt(number_of_weeks),
				"employee_id": e.name,
				"total": None
			})

	return resources

@frappe.whitelist()
def get_resources_total(start, end, group_by=None):
	assignments = get_assignments(start, end, group_by=group_by)

	total = defaultdict(float)
	for a in assignments:
		if not a.get("docstatus") == 1 or a.get("start") > getdate(end):
			continue

		calc_start = a.get("start") if getdate(end) >= a.get("start") >= getdate(start) else getdate(start)
		calc_end = a.get("end") if a.get("end") <= getdate(end) else getdate(end)
		number_of_days = date_diff(calc_end, calc_start) or 1
		total[a.get("resourceId")] += flt(a.get("duration")) * flt(number_of_days)

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
def get_tasks(projects=None):
	if not projects:
		projects = []
	else:
		projects = frappe.parse_json(projects)

	query_filters = {"status": ("in", ("Open", "Working", "Pending Review", "Overdue"))}
	if projects:
		query_filters.update({"project": ("in", projects)})

	return frappe.get_all("Task",
		filters=query_filters,
		fields=["name", "subject", "project", "exp_start_date", "exp_end_date", "_assign"], debug=False)

@frappe.whitelist()
def add_to_doc(doctype, name, assign_to=None):
	if not assign_to:
		assign_to = []
	else:
		assign_to = frappe.parse_json(assign_to)

	if assign_to:
		try:
			return add({
				"assign_to": assign_to,
				"doctype": doctype,
				"name": name
			})
		except Exception:
			pass
	else:
		frappe.msgprint(_("No user found for this employee"))

@frappe.whitelist()
def approve_shift_request(doctype, name):
	set_shift_request_status(doctype, name, "Approved")

@frappe.whitelist()
def reject_shift_request(doctype, name):
	set_shift_request_status(doctype, name, "Rejected")

def set_shift_request_status(doctype, name, status):
	doc = frappe.get_doc(doctype, name)
	doc.status = status
	doc.submit()

@frappe.whitelist()
def get_events(start, end, filters=None, group_by=None, with_tasks=False):
	if filters:
		filters = frappe.parse_json(filters)

	with_tasks = frappe.parse_json(with_tasks)

	out = get_assigned_tasks(start=start, end=end, filters=filters, group_by=group_by) if bool(with_tasks) else []

	if filters:
		filters.pop("projects")

	out.extend(get_holidays(start, end, filters))
	out.extend(get_leave_applications(start, end, filters))
	out.extend(get_trainings(start, end, filters))
	out.extend(get_assignment_requests(start, end, filters, group_by=group_by))
	out.extend(get_assignments(start, end, filters, group_by=group_by))
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
				"classNames": ["fc-background-event", "fc-yellow-stripped"],
				"doctype": "Holiday List",
				"docstatus": 0
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
	output = []
	for l in frappe.get_all("Leave Application",
			filters=filters if filters else {},
			fields=["name", "leave_type", "employee", "from_date", "to_date", "docstatus", "status"]
		):
		css_class = "fc-gray-stripped"
		if l.docstatus != 0:
			if l.status == "Approved" and l.docstatus == 1:
				css_class = "fc-green-stripped"
			else:
				css_class = "fc-gray-stripped"

		output.append(
			{
				"id": l.name,
				"resourceId": l.employee,
				"start": l.from_date,
				"end": l.to_date,
				"title": l.leave_type,
				"editable": 0,
				"classNames": ["fc-background-event", css_class],
				"doctype": "Leave Application",
				"docstatus": l.docstatus
			}
		)

	return output

def get_trainings(start, end, filters=None):
	query_filters = {
		"start_time": (">=", getdate(start)),
		"end_time": ("<=", getdate(end)),
		"docstatus": 1
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
			"classNames": ["fc-background-event", "fc-pacific-blue-stripped"],
			"doctype": "Training Event",
			"docstatus": e.docstatus
		}
		for e in frappe.get_all(
			"Training Event",
			filters=query_filters,
			fields=["name", "`tabTraining Event Employee`.employee", "start_time", "end_time", "event_name", "docstatus"]
		)
	]

def get_assignments(start, end, filters=None, group_by=None):
	from frappe.desk.reportview import get_filters_cond
	events = []
	query = "select name, start_date, end_date, employee_name, employee, docstatus, shift_type "

	meta = frappe.get_meta("Shift Assignment")
	if meta.has_field("department"):
		query += ", department "

	if meta.has_field("designation"):
		query += ", designation "

	if meta.has_field("project"):
		query += ", project "

	query += f"""from `tabShift Assignment` where
		(start_date >= {frappe.db.escape(start)}
		or (end_date <= {frappe.db.escape(end)} and end_date >= {frappe.db.escape(end)})
		or ({frappe.db.escape(start)} between start_date and end_date and {frappe.db.escape(end)} between start_date and end_date))
		"""

	if filters:
		query += get_filters_cond("Shift Assignment", filters, [])

	records = frappe.db.sql(query, as_dict=True, debug=False)

	has_group_by_field = False
	if group_by:
		has_group_by_field = meta.has_field(group_by.lower())

	shift_type_data = {}
	for d in records:
		if d.shift_type not in shift_type_data:
			shift_type_data[d.shift_type] = frappe.db.get_value("Shift Type", d.shift_type, ["start_time", "end_time"])

		resourceId = d.employee
		if group_by and has_group_by_field and d.get(group_by.lower()):
			resourceId += f"_{d.get(group_by.lower())}"

		daily_event_start = d.start_date
		daily_event_end = d.end_date if d.end_date else getdate()

		html_title = f'''
			<div>{cstr(d.shift_type)}</div>
			<div class="small">{d.get("department") or ""}{" | " if d.get("department") and d.get("designation") else ""}{d.get("designation") or ""}</div>
			<div class="small">
				<span>{format_time(shift_type_data.get(d.shift_type)[0])}</span>
					-
				<span>{format_time(shift_type_data.get(d.shift_type)[1])}</span>
			</div>
		'''
		e = {
			"id": d.name,
			"resourceId": resourceId,
			"doctype": "Shift Assignment",
			"docstatus": d.docstatus,
			"start": daily_event_start,
			"end": daily_event_end,
			"title": cstr(d.shift_type),
			"html_title": html_title,
			"start_time": shift_type_data.get(d.shift_type)[0],
			"end_time": shift_type_data.get(d.shift_type)[1],
			"editable": d.docstatus == 0,
			"classNames": ["fc-gray-bg"] if d.docstatus == 0 else (["fc-red-stripped"] if d.docstatus == 2 else ["fc-blue-bg"]),
			"duration": time_diff_in_hours(shift_type_data.get(d.shift_type)[1], shift_type_data.get(d.shift_type)[0]),
			"project": d.get("project"),
			"department": d.get("department"),
			"designation": d.get("designation"),
			"secondary_action": "frappe.client.cancel",
			"secondary_action_label": _("Cancel")
		}
		if e not in events:
			events.append(e)

	return events

def get_assignment_requests(start, end, filters=None, group_by=None):
	query_filters = frappe.parse_json(filters) if filters else {}
	query_filters.update({"docstatus": 0, "from_date": ("<=", getdate(end)), "to_date": (">=", getdate(start))})
	fields = ["name", "employee", "shift_type", "department", "status", "approver", "company", "from_date", "to_date"]

	meta = frappe.get_meta("Shift Request")
	if meta.has_field("designation"):
		fields.append("designation")

	if meta.has_field("project"):
		fields.append("project")

	has_group_by_field = False
	if group_by:
		has_group_by_field = meta.has_field(group_by.lower())

	requests = frappe.get_list("Shift Request",
		filters=query_filters,
		fields=fields
	)

	shift_type_data = {}
	events = []
	for d in requests:
		if d.shift_type not in shift_type_data:
			shift_type_data[d.shift_type] = frappe.db.get_value("Shift Type", d.shift_type, ["start_time", "end_time"])

		resourceId = d.employee
		if group_by and has_group_by_field and d.get(group_by.lower()):
			resourceId += f"_{d.get(group_by.lower())}"

		daily_event_start = d.from_date
		daily_event_end = d.to_date if d.to_date else getdate()

		html_title = f'''
			<div>{cstr(d.shift_type)}</div>
			<div class="small">{d.get("department") or ""}{" | " if d.get("department") and d.get("designation") else ""}{d.get("designation") or ""}</div>
			<div class="small">
				<span>{format_time(shift_type_data.get(d.shift_type)[0])}</span>
					-
				<span>{format_time(shift_type_data.get(d.shift_type)[1])}</span>
			</div>
		'''
		e = {
			"id": d.name,
			"resourceId": resourceId,
			"doctype": "Shift Request",
			"docstatus": d.docstatus,
			"start": daily_event_start,
			"end": daily_event_end,
			"title": cstr(d.shift_type),
			"html_title": html_title,
			"start_time": shift_type_data.get(d.shift_type)[0],
			"end_time": shift_type_data.get(d.shift_type)[1],
			"editable": d.docstatus == 0,
			"classNames": ["fc-green-bg"],
			"duration": time_diff_in_hours(shift_type_data.get(d.shift_type)[1], shift_type_data.get(d.shift_type)[0]),
			"project": d.get("project"),
			"department": d.get("department"),
			"designation": d.get("designation"),
			"primary_action": "erpnext.hr.page.resource_planning_view.resource_planning_view.approve_shift_request",
			"primary_action_label": _("Approve"),
			"secondary_action": "erpnext.hr.page.resource_planning_view.resource_planning_view.reject_shift_request",
			"secondary_action_label": _("Reject"),
		}
		if e not in events:
			events.append(e)

	return events

def get_assigned_tasks(start, end, filters=None, group_by=None):
	query_filters = {"status": ("in", ("Open", "Working", "Pending Review", "Overdue"))}

	if start and end:
		start_date = add_days(getdate(start), -1)
		end_date = add_days(getdate(end), 1)
		query_filters.update({f"ifnull(exp_start_date, {frappe.db.escape(start)})": (">=", start_date), f"ifnull(exp_end_date, {frappe.db.escape(end)})": (">=", end_date)})

	if filters.get("projects"):
		query_filters.update({"project": ("in", filters.get("projects"))})

	fields = ["name", "subject", "project", "exp_start_date", "exp_end_date", "_assign", "docstatus", "color"]

	if group_by:
		has_group_by_field = frappe.get_meta("Task").has_field(group_by.lower())
		if has_group_by_field:
			fields.append(group_by.lower())

	tasks = []
	user_map = defaultdict(str)
	for task in frappe.get_all("Task",
		filters=query_filters,
		fields=fields):
		for assigned in frappe.parse_json(task._assign or []):
			if not user_map.get(assigned):
				user_map[assigned] = frappe.db.get_value("Employee", dict(user_id=assigned))

			formatted_start_date = format_date(task.exp_start_date) if task.exp_start_date else _("No start date")
			formatted_end_date = format_date(task.exp_end_date) if task.exp_end_date else _("No end date")

			resourceId = user_map.get(assigned)
			if group_by and has_group_by_field and task.get(group_by.lower()):
				resourceId += f"_{task.get(group_by.lower())}"

			tasks.append({
				"id": f"{task.name}{assigned}",
				"resourceId": resourceId,
				"start": task.exp_start_date or start,
				"end": task.exp_end_date or end,
				"title": task.subject,
				"html_title": f'<div>{cstr(task.subject)}</div><div class="small"><span>{(task.project + " | ") if task.project else ""}</span><span>{formatted_start_date}</span>-<span>{formatted_end_date}</span></div>',
				"editable": 1,
				"borderColor": task.color,
				"textColor": task.color,
				"classNames": ["fc-stripped-event"],
				"doctype": "Task",
				"docstatus": task.docstatus,
				"project": task.get("project")
			})

	return tasks

