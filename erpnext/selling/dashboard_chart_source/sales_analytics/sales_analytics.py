# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import add_months, get_year_start, nowdate
from frappe.utils.dashboard import cache_source

from erpnext import get_default_company
from erpnext.selling.report.sales_analytics.sales_analytics import Analytics


@frappe.whitelist()
@cache_source
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	filters = frappe.parse_json(filters)
	limit = filters.get("limit")

	start_date = from_date or add_months(nowdate(), -3)
	if filters.get("range"):
		if filters.get("range") == "Quarterly":
			start_date = get_year_start(nowdate())
		elif filters.get("range") == "Yearly":
			start_date = get_year_start(add_months(nowdate(), -24))
		elif filters.get("range") == "Weekly":
			start_date = add_months(nowdate(), -1)

	if not filters.get("from_date"):
		filters["from_date"] = start_date

	if not filters.get("to_date"):
		filters["to_date"] = nowdate()

	if not filters.get("company"):
		filters["company"] = get_default_company()

	columns, data, message, chart, report_summary, skip_total_row = Analytics(filters).run()

	data = sort_and_filter_data(data, limit)

	length = len(columns)

	if filters.tree_type in ["Customer", "Supplier"]:
		labels, datasets = add_labels_and_values(columns[2 : length - 1], data)
	elif filters.tree_type == "Item":
		labels, datasets = add_labels_and_values(columns[3 : length - 1], data)
	else:
		labels, datasets = add_labels_and_values(columns[1 : length - 1], data)

	chart = {"labels": labels, "datasets": datasets, "type": "bar"}

	if filters["value_quantity"] == "Value":
		chart["fieldtype"] = "Currency"
	else:
		chart["fieldtype"] = "Float"

	return chart


def sort_and_filter_data(data, limit=None):
	data_with_total = [d for d in data if d.get("total") and d.get("indent", 1) > 0]

	filtered_data = []

	if data_with_total and not data_with_total[0].get("indent"):
		filtered_data = data_with_total

	else:
		grouped_data = []
		subgroup = []
		for d in data_with_total:
			if d.get("indent") == 1 and subgroup:
				grouped_data.append(subgroup)
				subgroup = []

			subgroup.append(d)

		if subgroup:
			grouped_data.append(subgroup)

		for group in grouped_data:
			if len(group) == 1:
				filtered_data.append(group[0])
			else:
				max_value = max(group, key=lambda g: g["indent"]).get("indent")
				for g in group:
					if g.get("indent") == max_value:
						filtered_data.append(g)

	if limit:
		filtered_data.sort(key=lambda x: x["total"], reverse=True)
		filtered_data = filtered_data[:limit]

	return filtered_data


def add_labels_and_values(columns, data):
	labels = []
	datasets = []

	for col in columns:
		labels.append(col.get("label"))

	for d in data:
		values = []
		for col in columns:
			values.append(d.get(col.get("fieldname")))

		datasets.append({"name": d.get("entity"), "values": values})

	return labels, datasets
