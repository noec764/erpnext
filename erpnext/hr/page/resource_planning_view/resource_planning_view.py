from collections import defaultdict

import frappe
from frappe import _
from frappe.desk.form.assign_to import add
from frappe.utils import (
	add_days,
	cstr,
	date_diff,
	flt,
	format_date,
	format_time,
	getdate,
	nowdate,
	time_diff_in_hours,
)
from frappe.utils.dateutils import get_dates_from_timegrain
from frappe.utils.nestedset import get_descendants_of

CALENDAR_MAP = {
	0: "monday",
	1: "tuesday",
	2: "wednesday",
	3: "thursday",
	4: "friday",
	5: "saturday",
	6: "sunday",
}


@frappe.whitelist()
def get_resources(
	company,
	start,
	end,
	employee=None,
	department=None,
	group_by=None,
	group_by_value=None,
	resources_view="Employee",
	with_tasks=False,
):
	return ResourceQuery(
		company=company,
		start=start,
		end=end,
		employee=employee,
		department=department,
		group_by=group_by,
		group_by_value=group_by_value,
		resources_view=resources_view,
		with_tasks=with_tasks,
	).get_resources()


class ResourceQuery:
	def __init__(self, **kwargs):
		for (k, v) in kwargs.items():
			setattr(self, k, v)

		self.start = getdate(self.start)
		self.end = getdate(self.end)
		self.groups = defaultdict(set)
		self.resource_list = []
		self.resources_dict = {}
		self.resources = []

	def get_resources(self):
		if self.resources_view == "Employee":
			self.get_employees()
			self.get_working_time()
		elif self.resources_view == "Shift Type":
			self.get_shift_resources()

		if self.group_by:
			self.get_group_by_data()

		if self.group_by and self.groups:
			self.get_group_by_resources()

		if not self.resources:
			self.get_individual_resources()

		return self.resources

	def get_employees(self):
		query_filters = {"status": "Active", "company": self.company}

		if self.department and not self.group_by == "Department":
			query_filters.update(
				{"department": ("in", [self.department] + get_descendants_of("Department", self.department))}
			)

		if self.employee:
			query_filters.update({"name": self.employee})

		self.resource_list = frappe.get_list(
			"Employee",
			filters=query_filters,
			fields=["name", "employee_name", "department", "company", "user_id", "designation"],
		)

		self.resources_dict = {
			x.name: [x.company, x.user_id, x.employee_name] for x in self.resource_list
		}

	def get_working_time(self):
		self.working_time = {
			x.employee: {
				"weekly_working_hours": x.weekly_working_hours,
				"monday": x.monday,
				"tuesday": x.tuesday,
				"wednesday": x.wednesday,
				"thursday": x.thursday,
				"friday": x.friday,
				"saturday": x.saturday,
				"sunday": x.sunday,
			}
			for x in frappe.get_all(
				"Employment Contract",
				filters={
					"employee": ("in", self.resources_dict.keys()),
					"date_of_joining": ("<=", nowdate()),
					"ifnull(relieving_date, '3999-12-31')": (">=", nowdate()),
				},
				fields=[
					"employee",
					"weekly_working_hours",
					"monday",
					"tuesday",
					"wednesday",
					"thursday",
					"friday",
					"saturday",
					"sunday",
				],
			)
		}

	def calculate_working_time(self, employee):
		if self.resources_view != "Employee":
			return 0

		# FullCalendar returns the next day in its API
		end = add_days(self.end, -1)
		holidays_for_employee = [
			getdate(h.holiday_date) for h in get_holidays_for_employee(employee, self.start, end)
		]

		total = 0.0
		for date in get_dates_from_timegrain(self.start, end):
			if date not in holidays_for_employee:
				total += self.working_time.get(employee, {}).get(CALENDAR_MAP.get(date.weekday()), 0.0)
		return total

	def get_group_by_data(self):
		if self.resources_view == "Employee":
			self.get_group_by_data_for_employees()
		elif self.resources_view == "Shift Type":
			self.get_group_by_data_for_shift_types()

	def get_group_by_data_for_employees(self):
		event_query_filters = {"projects": []}
		if self.employee:
			event_query_filters.update({"employee": self.employee})
		if self.department:
			event_query_filters.update(
				{"department": ("in", [self.department] + get_descendants_of("Department", self.department))}
			)

		events = get_events(self.start, self.end, event_query_filters, with_tasks=self.with_tasks)

		for event in events:
			emp = event.get("employee") or event.get("resourceId")
			self.group_by_data = event.get(self.group_by.lower())
			if self.group_by_data:
				self.groups[self.group_by_data].add(emp)

	def get_group_by_data_for_shift_types(self):
		meta = frappe.get_meta(self.group_by)
		query_filters = {"company": self.company} if meta.has_field("company") else {}
		if self.department and self.group_by == "Department":
			query_filters.update(
				{"name": ("in", [self.department] + get_descendants_of("Department", self.department))}
			)
		elif self.department:
			query_filters.update(
				{"department": ("in", [self.department] + get_descendants_of("Department", self.department))}
			)

		group_by = frappe.get_list(self.group_by, filters=query_filters)

		for group in group_by:
			for res in self.resource_list:
				self.groups[group.name].add(res.get("name"))

	def get_group_by_resources(self):
		for group in self.groups:
			for emp in self.groups[group]:
				if self.resources_dict.get(emp):
					self.resources.append(
						{
							"id": f"{emp}_{group}",
							"title": self.resources_dict.get(emp)[2],
							self.group_by.lower(): group or "N/A",
							"company": self.resources_dict.get(emp)[0],
							"user_id": self.resources_dict.get(emp)[1],
							"working_time": self.calculate_working_time(emp),
							"employee_id": emp,
							"total": None,
						}
					)

	def get_individual_resources(self):
		for e in self.resource_list:
			self.resources.append(
				{
					"id": e.name,
					"title": e.employee_name or e.name,
					"department": e.department,
					"designation": e.designation,
					"company": e.company,
					"user_id": e.user_id,
					"working_time": self.calculate_working_time(e.name),
					"employee_id": e.name,
					"total": None,
				}
			)

	def get_shift_resources(self):
		query_filters = {"name": self.group_by_value} if self.group_by_value else {}
		self.resource_list = get_shift_types(query_filters)
		self.resources_dict = {
			x.get("name"): [x.get("company"), None, x.get("name")] for x in self.resource_list
		}


@frappe.whitelist()
def get_resources_total(start, end, group_by=None):
	assignments = get_assignments(start, end, group_by=group_by)

	total = defaultdict(float)
	for a in assignments:
		if not a.get("docstatus") == 1 or a.get("start") > getdate(end):
			continue

		calc_start = (
			a.get("start") if getdate(end) >= a.get("start") >= getdate(start) else getdate(start)
		)
		calc_end = a.get("end") if a.get("end") <= getdate(end) else getdate(end)
		number_of_days = date_diff(calc_end, calc_start) or 1
		total[a.get("resourceId")] += flt(a.get("duration")) * flt(number_of_days)

	return total


@frappe.whitelist()
def get_shift_types(query_filters=None):
	if not query_filters:
		query_filters = {}

	query_fields = ["name", "start_time", "end_time"]
	meta = frappe.get_meta("Shift Type")
	if meta.has_field("company"):
		query_fields.append("company")

	if meta.has_field("department"):
		query_fields.append("department")

	return [
		frappe._dict(
			{
				"name": st.name,
				"startTime": st.start_time,
				"duration": time_diff_in_hours(st.end_time, st.start_time),
			},
			**st,
		)
		for st in frappe.get_all("Shift Type", filters=query_filters, fields=query_fields)
	]


@frappe.whitelist()
def get_tasks(start, end, projects=None):
	if not projects:
		projects = []
	else:
		projects = frappe.parse_json(projects)

	query_filters = {
		"status": ("in", ("Open", "Working", "Pending Review", "Overdue")),
		"ifnull(exp_end_date, '2999-12-31')": (">=", start),
		"ifnull(exp_start_date, '1900-01-01')": ("<=", end),
	}
	if projects:
		query_filters.update({"project": ("in", projects)})

	return frappe.get_all(
		"Task",
		filters=query_filters,
		fields=["name", "subject", "project", "exp_start_date", "exp_end_date", "_assign"],
	)


@frappe.whitelist()
def add_to_doc(doctype, name, assign_to=None):
	if not assign_to:
		assign_to = []
	else:
		assign_to = frappe.parse_json(assign_to)

	if assign_to:
		try:
			return add({"assign_to": assign_to, "doctype": doctype, "name": name})
		except Exception:
			pass
	else:
		frappe.msgprint(_("No user found for this employee"))


@frappe.whitelist()
def approve_shift_request(doctype, name):
	return set_shift_request_status(doctype, name, "Approved")


@frappe.whitelist()
def reject_shift_request(doctype, name):
	return set_shift_request_status(doctype, name, "Rejected")


def set_shift_request_status(doctype, name, status):
	doc = frappe.get_doc(doctype, name)
	doc.status = status
	return doc.submit()


@frappe.whitelist()
def submit_shift_assignment(doctype, name):
	return frappe.get_doc(doctype, name).submit()


@frappe.whitelist()
def get_events(
	start, end, filters=None, group_by=None, with_tasks=False, resources_view="Employee"
):
	if filters:
		filters = frappe.parse_json(filters)

	if resources_view == "Shift Type":
		if filters:
			filters.pop("projects")

		out = get_shift_type_totals(start=start, end=end, filters=filters, group_by=group_by)
	else:
		with_tasks = frappe.parse_json(with_tasks)

		out = (
			get_assigned_tasks(start=start, end=end, filters=filters, group_by=group_by)
			if bool(with_tasks)
			else []
		)

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

	employees = frappe.get_all("Employee", filters=query_filters, pluck="name")

	holidays = []
	for employee in employees:
		holidays_for_employee = get_holidays_for_employee(employee, start_date, end_date)

		for hle in holidays_for_employee:
			holidays.append(
				{
					"id": hle.name,
					"resourceId": employee,
					"start": hle.holiday_date,
					"end": hle.holiday_date,
					"title": hle.description,
					"editable": 0,
					"borderColor": "var(--yellow-200)",
					"classNames": ["fc-background-event", "fc-yellow-stripped"],
					"doctype": "Holiday List",
					"docname": hle.name,
					"docstatus": 0,
				}
			)

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

	holidays = frappe.db.sql(
		"""select name, holiday_date, description from `tabHoliday`
		where
			parent in %(holiday_list)s
			and holiday_date >= %(start_date)s
			and holiday_date <= %(end_date)s""",
		{"holiday_list": tuple(total_holidays), "start_date": start_date, "end_date": end_date},
		as_dict=True,
	)

	return holidays


def get_leave_applications(start, end, filters=None):
	output = []
	for l in frappe.get_all(
		"Leave Application",
		filters=filters if filters else {},
		fields=["name", "leave_type", "employee", "from_date", "to_date", "docstatus", "status"],
	):
		css_class = "fc-gray-stripped"
		border_color = "var(--gray-200)"
		if l.docstatus != 0:
			if l.status == "Approved" and l.docstatus == 1:
				css_class = "fc-green-stripped"
				border_color = "var(--green-200)"

		output.append(
			{
				"id": l.name,
				"resourceId": l.employee,
				"start": l.from_date,
				"end": l.to_date,
				"title": l.leave_type,
				"editable": 0,
				"borderColor": border_color,
				"classNames": ["fc-background-event", css_class],
				"doctype": "Leave Application",
				"docname": l.name,
				"docstatus": l.docstatus,
			}
		)

	return output


def get_trainings(start, end, filters=None):
	query_filters = {
		"start_time": (">=", getdate(start)),
		"end_time": ("<=", getdate(end)),
		"docstatus": 1,
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
			"borderColor": "var(--pacific-blue-200)",
			"classNames": ["fc-background-event", "fc-pacific-blue-stripped"],
			"doctype": "Training Event",
			"docname": e.name,
			"docstatus": e.docstatus,
		}
		for e in frappe.get_all(
			"Training Event",
			filters=query_filters,
			fields=[
				"name",
				"`tabTraining Event Employee`.employee",
				"start_time",
				"end_time",
				"event_name",
				"docstatus",
			],
		)
	]


def get_assignments(start, end, filters=None, group_by=None, return_records=False):
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
	if return_records:
		return records

	has_group_by_field = False
	if group_by:
		has_group_by_field = meta.has_field(group_by.lower())

	shift_type_data = {}
	for d in records:
		if d.shift_type not in shift_type_data:
			shift_type_data[d.shift_type] = frappe.db.get_value(
				"Shift Type", d.shift_type, ["start_time", "end_time"]
			)

		resourceId = d.employee
		if group_by and has_group_by_field and d.get(group_by.lower()):
			resourceId += f"_{d.get(group_by.lower())}"

		daily_event_start = d.start_date
		daily_event_end = d.end_date if d.end_date else getdate()

		html_title = f"""
			<div>{cstr(d.shift_type)}</div>
			<div class="small">{d.get("department") or ""}{" | " if d.get("department") and d.get("designation") else ""}{d.get("designation") or ""}</div>
			<div class="small">
				<span>{format_time(shift_type_data.get(d.shift_type)[0])}</span>
					-
				<span>{format_time(shift_type_data.get(d.shift_type)[1])}</span>
			</div>
		"""
		e = {
			"id": d.name,
			"resourceId": resourceId,
			"doctype": "Shift Assignment",
			"docname": d.name,
			"docstatus": d.docstatus,
			"start": daily_event_start,
			"end": daily_event_end,
			"title": cstr(d.shift_type),
			"html_title": html_title,
			"start_time": shift_type_data.get(d.shift_type)[0],
			"end_time": shift_type_data.get(d.shift_type)[1],
			"editable": d.docstatus == 0,
			"borderColor": "var(--gray-200)"
			if d.docstatus == 0
			else ("var(--red-200)" if d.docstatus == 2 else "var(--blue-400)"),
			"classNames": ["fc-gray-bg"]
			if d.docstatus == 0
			else (["fc-red-stripped"] if d.docstatus == 2 else ["fc-blue-bg"]),
			"duration": time_diff_in_hours(
				shift_type_data.get(d.shift_type)[1], shift_type_data.get(d.shift_type)[0]
			),
			"project": d.get("project"),
			"department": d.get("department"),
			"designation": d.get("designation"),
			"shift_type": d.get("shift_type"),
		}

		if d.docstatus == 0:
			e.update(
				{
					"primary_action": "erpnext.hr.page.resource_planning_view.resource_planning_view.submit_shift_assignment",
					"primary_action_label": _("Submit"),
					"secondary_action": "frappe.client.delete",
					"secondary_action_label": _("Delete"),
				}
			)
		elif d.docstatus == 1:
			e.update({"secondary_action": "frappe.client.cancel", "secondary_action_label": _("Cancel")})

		if e not in events:
			events.append(e)

	return events


def get_assignment_requests(start, end, filters=None, group_by=None):
	query_filters = frappe.parse_json(filters) if filters else {}
	query_filters.update(
		{"docstatus": 0, "from_date": ("<=", getdate(end)), "to_date": (">=", getdate(start))}
	)
	fields = [
		"name",
		"employee",
		"shift_type",
		"department",
		"status",
		"approver",
		"company",
		"from_date",
		"to_date",
	]

	meta = frappe.get_meta("Shift Request")
	if meta.has_field("designation"):
		fields.append("designation")

	if meta.has_field("project"):
		fields.append("project")

	has_group_by_field = False
	if group_by:
		has_group_by_field = meta.has_field(group_by.lower())

	requests = frappe.get_list("Shift Request", filters=query_filters, fields=fields)

	shift_type_data = {}
	events = []
	for d in requests:
		if d.shift_type not in shift_type_data:
			shift_type_data[d.shift_type] = frappe.db.get_value(
				"Shift Type", d.shift_type, ["start_time", "end_time"]
			)

		resourceId = d.employee
		if group_by and has_group_by_field and d.get(group_by.lower()):
			resourceId += f"_{d.get(group_by.lower())}"

		daily_event_start = d.from_date
		daily_event_end = d.to_date if d.to_date else getdate()

		html_title = f"""
			<div>{cstr(d.shift_type)}</div>
			<div class="small">{d.get("department") or ""}{" | " if d.get("department") and d.get("designation") else ""}{d.get("designation") or ""}</div>
			<div class="small">
				<span>{format_time(shift_type_data.get(d.shift_type)[0])}</span>
					-
				<span>{format_time(shift_type_data.get(d.shift_type)[1])}</span>
			</div>
		"""
		e = {
			"id": d.name,
			"resourceId": resourceId,
			"doctype": "Shift Request",
			"docname": d.name,
			"docstatus": d.docstatus,
			"start": daily_event_start,
			"end": daily_event_end,
			"title": cstr(d.shift_type),
			"html_title": html_title,
			"start_time": shift_type_data.get(d.shift_type)[0],
			"end_time": shift_type_data.get(d.shift_type)[1],
			"editable": d.docstatus == 0,
			"borderColor": "var(--green-300)",
			"classNames": ["fc-green-bg"],
			"duration": time_diff_in_hours(
				shift_type_data.get(d.shift_type)[1], shift_type_data.get(d.shift_type)[0]
			),
			"project": d.get("project"),
			"department": d.get("department"),
			"designation": d.get("designation"),
			"shift_type": d.get("shift_type"),
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
		query_filters.update(
			{
				f"ifnull(exp_start_date, {frappe.db.escape(start)})": (">=", start_date),
				f"ifnull(exp_end_date, {frappe.db.escape(end)})": (">=", end_date),
			}
		)

	if filters.get("projects"):
		query_filters.update({"project": ("in", filters.get("projects"))})

	fields = [
		"name",
		"subject",
		"project",
		"exp_start_date",
		"exp_end_date",
		"_assign",
		"docstatus",
		"color",
	]

	if group_by:
		has_group_by_field = frappe.get_meta("Task").has_field(group_by.lower())
		if has_group_by_field:
			fields.append(group_by.lower())

	tasks = []
	user_map = defaultdict(str)
	for task in frappe.get_all("Task", filters=query_filters, fields=fields):
		for assigned in frappe.parse_json(task._assign or []):
			if not user_map.get(assigned):
				user_map[assigned] = frappe.db.get_value("Employee", dict(user_id=assigned))

			formatted_start_date = (
				format_date(task.exp_start_date) if task.exp_start_date else _("No start date")
			)
			formatted_end_date = format_date(task.exp_end_date) if task.exp_end_date else _("No end date")

			resourceId = user_map.get(assigned) or ""
			if group_by and has_group_by_field and task.get(group_by.lower()):
				resourceId += f"_{task.get(group_by.lower())}"

			tasks.append(
				{
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
					"docname": task.name,
					"docstatus": task.docstatus,
					"project": task.get("project"),
				}
			)

	return tasks


def get_shift_type_totals(start, end, filters, group_by=None):
	shift_types = get_shift_types()
	assignments = get_assignments(start, end, filters, return_records=True)

	meta = frappe.get_meta("Shift Assignment")
	has_group_by_field = False
	if group_by:
		has_group_by_field = meta.has_field(group_by.lower())

	out = []
	for shift_type in shift_types:
		for date in get_dates_from_timegrain(start, end):

			ass_by_res = defaultdict(int)
			for assignment in assignments:
				resourceId = shift_type.get("name")

				if group_by and has_group_by_field and assignment.get(group_by.lower()):
					resourceId += f"_{assignment.get(group_by.lower())}"

				if assignment.get("shift_type") == shift_type.get("name") and (
					getdate(assignment.get("start_date")) <= date and getdate(assignment.get("end_date")) >= date
				):
					ass_by_res[resourceId] += 1

			for res in ass_by_res:
				out.append(
					{
						"resourceId": res,
						"start": date,
						"end": date,
						"title": _("{0} employees").format(str(ass_by_res[res])),
						"classNames": ["fc-dark-green-bg" if ass_by_res[res] > 0 else "fc-dark-orange-bg"],
					}
				)

	return out
