# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_months, nowdate
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
	filters["from_date"] = add_months(nowdate(), -3)
	filters["to_date"] = nowdate()
	if not filters.get("company"):
		filters["company"] = get_default_company()

	columns, data, message, chart, report_summary, skip_total_row = Analytics(filters).run()

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


def add_labels_and_values(columns, data):
	labels = []
	datasets = []
	column_names = [col.get("fieldname") for col in columns]

	for col in columns:
		labels.append(col.get("label"))

	for d in data:
		values = []
		report_values = [value for key, value in d.items() if key in column_names]
		if not all(report_values) or d.get("indent") != 1:
			continue

		for col in columns:
			values.append(d.get(col.get("fieldname")))

		datasets.append({"name": d.get("entity"), "values": values})

	return labels, datasets
