# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt

import itertools

import frappe
from frappe import _
from frappe.utils.dashboard import cache_source


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
	from erpnext.accounts.report.financial_statements import get_data, get_period_list

	labels, datasets = [], []
	if filters:
		filters = frappe.parse_json(filters)

		report_filters = frappe._dict(
			{
				"company": filters.get("company"),
				"filter_based_on": "Fiscal Year",
				"from_fiscal_year": filters.get("fiscal_year") or frappe.db.get_default("Fiscal Year"),
				"to_fiscal_year": filters.get("fiscal_year") or frappe.db.get_default("Fiscal Year"),
				"periodicity": "Yearly",
			}
		)

		period_list = get_period_list(
			report_filters.from_fiscal_year,
			report_filters.to_fiscal_year,
			None,
			None,
			report_filters.filter_based_on,
			report_filters.periodicity,
			company=report_filters.company,
		)

		pl_data = get_data(
			filters.company,
			"Income" if filters.get("income_or_expenses") == "Income" else "Expense",
			"Credit" if filters.get("income_or_expenses") == "Income" else "Debit",
			period_list,
			filters=filters,
			accumulated_values=filters.accumulated_values,
			ignore_closing_entries=True,
			ignore_accumulated_values_for_fy=True,
		)

		data = {row.get("account"): row.get("total") for row in pl_data if row.get("is_group") == 0.0}

		sorted_data = dict(sorted(data.items(), key=lambda item: item[1], reverse=True))

		if filters.get("limit"):
			sorted_data = dict(itertools.islice(sorted_data.items(), filters.get("limit")))

		dataset = {"name": _("Income"), "values": []}
		for d in sorted_data:
			labels.append(d.rsplit("-", 1)[0])
			dataset["values"].append(sorted_data[d])

		datasets.append(dataset)

	chart = {
		"labels": labels,
		"datasets": datasets,
		"type": "bar",
		"fieldtype": "Currency",
	}

	return chart
