# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from erpnext.accounts.report.financial_statements import (get_period_list, get_columns, \
	get_additional_conditions, add_total_row, accumulate_values_into_parents, get_accounts, \
	filter_accounts, prepare_data, filter_out_zero_value_rows, get_appropriate_currency)
from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (get_chart_data, \
	get_net_profit_loss)
from frappe.utils import flt
from collections import defaultdict

from six import itervalues, iteritems

def execute(filters=None):
	period_list = get_period_list(filters.from_fiscal_year, filters.to_fiscal_year,
		filters.periodicity, filters.accumulated_values, filters.company)

	income, income_unreconciled = get_data(filters.company, "Income", "Credit", period_list, filters = filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy= True)

	expense, expense_unreconciled = get_data(filters.company, "Expense", "Debit", period_list, filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True, ignore_accumulated_values_for_fy= True)

	unreconciled_amount = get_unreconciled_amount(income_unreconciled, period_list, \
			filters.company, filters.presentation_currency)

	net_profit_loss = get_net_profit_loss(income, expense, period_list, filters.company, filters.presentation_currency)

	data = []
	data.extend(income or [])
	data.extend(expense or [])
	if net_profit_loss:
		data.append(net_profit_loss)
	if unreconciled_amount:
		data.append([])
		data.append(unreconciled_amount)

	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)

	chart = get_chart_data(filters, columns, income, expense, net_profit_loss)

	return columns, data, None, chart

def get_data(company, root_type, balance_must_be, period_list, filters=None,
		accumulated_values=1, only_current_fiscal_year=True, ignore_closing_entries=False,
		ignore_accumulated_values_for_fy=False):
	cash_bank_accounts = get_cash_bank_accounts(company)
	accounts = get_accounts(company, root_type)

	if not accounts or not cash_bank_accounts:
		return None

	accounts, accounts_by_name, parent_children_map = filter_accounts(accounts)

	company_currency = get_appropriate_currency(company, filters)

	cash_bank_entries = []
	for account in cash_bank_accounts:
		cash_bank_entries.extend(frappe.get_all("GL Entry", filters={"account": account.name}, fields=["name", \
			"posting_date", "account", "fiscal_year", "debit", "credit", "account_currency", "voucher_type", \
			"voucher_no", "debit_in_account_currency", "credit_in_account_currency"]))

	cash_bank_entries = merge_similar_entries(cash_bank_entries)

	gl_entries_by_account = {}
	unreconcilied_payments = {}
	cb_accounts_by_name = {}
	for entry in cash_bank_entries:
		for root in frappe.db.sql("""select lft, rgt from tabAccount
		where root_type=%s and ifnull(parent_account, '') = ''""", root_type, as_dict=1):
			set_payment_entries_by_account(
				company,
				period_list[0]["year_start_date"] if only_current_fiscal_year else None,
				period_list[-1]["to_date"],
				root.lft, root.rgt, filters,
				gl_entries_by_account,
				unreconcilied_payments,
				entry,
				ignore_closing_entries=ignore_closing_entries
			)

	calculate_values(
		accounts_by_name, gl_entries_by_account, period_list, accumulated_values, \
		ignore_accumulated_values_for_fy, True)

	accumulate_values_into_parents(accounts, accounts_by_name, period_list, accumulated_values)
	out = prepare_data(accounts, balance_must_be, period_list, company_currency)
	out = filter_out_zero_value_rows(out, parent_children_map)

	if unreconcilied_payments:
		cash_bank_accounts, cb_accounts_by_name, parent_children_map = filter_accounts(cash_bank_accounts)

		calculate_values(
			cb_accounts_by_name, unreconcilied_payments, period_list, accumulated_values, \
			ignore_accumulated_values_for_fy)

	if out:
		add_total_row(out, root_type, balance_must_be, period_list, company_currency)

	return out, cb_accounts_by_name

def get_cash_bank_accounts(company):
	return frappe.db.sql("""
		select name, account_number, parent_account, lft, rgt, root_type, report_type, account_name
		from `tabAccount`
		where company=%s and account_type in ('Bank', 'Cash') order by lft""", company, as_dict=True)

def set_payment_entries_by_account(company, from_date, to_date, root_lft, root_rgt, \
	filters, gl_entries_by_account, unreconcilied_payments, bank_entry, ignore_closing_entries=False):
	"""Returns a dict like { "account": [gl entries], ... }"""

	additional_conditions = get_additional_conditions(from_date, ignore_closing_entries, filters)

	accounts = frappe.db.sql_list("""select name from `tabAccount`
		where lft >= %s and rgt <= %s""", (root_lft, root_rgt))

	additional_conditions += " and account in ({})"\
		.format(", ".join([frappe.db.escape(d) for d in accounts]))

	additional_conditions = add_voucher_filter(additional_conditions, bank_entry)
	
	if additional_conditions:

		gl_entries = frappe.db.sql("""select name, posting_date, account, debit, credit, is_opening, \
			fiscal_year, debit_in_account_currency, credit_in_account_currency, account_currency, \
			voucher_type, voucher_no
			from `tabGL Entry`
			where company=%(company)s
			{additional_conditions}
			and posting_date <= %(to_date)s
			order by account, posting_date""".format(additional_conditions=additional_conditions),
			{
				"company": company,
				"from_date": from_date,
				"to_date": to_date,
				"cost_center": filters.cost_center,
				"project": filters.project
			},
			as_dict=True)

		if filters and filters.get('presentation_currency'):
			convert_to_presentation_currency(gl_entries, get_currency(filters))

		for entry in gl_entries:
			entry["cb_credit"]=bank_entry["credit"]
			entry["cb_debit"]=bank_entry["debit"]
			entry["cb_posting_date"]=bank_entry["posting_date"]
			gl_entries_by_account.setdefault(entry.account, []).append(entry)

		return gl_entries_by_account

	else:
		unreconcilied_payments.setdefault(bank_entry.account, []).append(bank_entry)

		return unreconcilied_payments

def add_voucher_filter(additional_conditions, bank_entry):
	linked_vouchers = []
	if bank_entry["voucher_type"] == "Payment Entry":
		linked_vouchers = frappe.get_all("Payment Entry Reference", \
			filters={"parenttype": "Payment Entry", "parent": bank_entry["voucher_no"]}, \
			fields=["reference_doctype", "reference_name"])

	elif bank_entry["voucher_type"] == "Journal Entry":
		linked_vouchers = frappe.get_all("Journal Entry Account", \
			filters={"parenttype": "Journal Entry", "parent": bank_entry["voucher_no"]}, \
			fields=["reference_type as reference_doctype", "reference_name"])


	if linked_vouchers:
		linked_vouchers = [dict(y) for y in set(tuple(x.items()) for x in linked_vouchers)]

		voucher_conditions = []
		for voucher in linked_vouchers:
			if voucher["reference_doctype"] is not None and voucher["reference_name"] is not None:
				voucher_conditions.append("(voucher_type={0} and voucher_no={1})" \
				.format(frappe.db.escape(voucher["reference_doctype"]), frappe.db.escape(voucher["reference_name"])))

		voucher_conditions = " or ".join(voucher_conditions)
		
		if voucher_conditions:
			additional_conditions += " and ({})".format(voucher_conditions)

			return additional_conditions
	
	return None

def calculate_values(accounts_by_name, gl_entries_by_account, period_list, \
	accumulated_values, ignore_accumulated_values_for_fy, merge=False):
	tree = lambda: defaultdict(tree)
	reconciled_entries = tree()
	for entries in itervalues(gl_entries_by_account):
		if merge:
			entries = merge_similar_entries(entries, True)
		for entry in entries:
			if merge:
				reconciled_entries = add_to_reconciled_data(reconciled_entries, entry)

			d = accounts_by_name.get(entry.account)
			if not d:
				frappe.msgprint(
					_("Could not retrieve information for {0}.".format(entry.account)), title="Error",
					raise_exception=1
				)

			posting_date = entry.cb_posting_date if "cb_posting_date" in entry else  entry.posting_date
			debit = min(entry.debit, entry.cb_credit) if "cb_credit" in entry else entry.debit
			credit = min(entry.credit, entry.cb_debit) if "cb_debit" in entry else entry.credit

			for period in period_list:
				# check if posting date is within the period

				if posting_date <= period.to_date:
					if (accumulated_values or posting_date >= period.from_date) and \
						(not ignore_accumulated_values_for_fy or
							entry.fiscal_year == period.to_date_fiscal_year):

						if merge:
							if flt(reconciled_entries[entry.voucher_type][entry.voucher_no]["rec_credit"]) <= \
								flt(reconciled_entries[entry.voucher_type][entry.voucher_no]["total_credit"]) and \
								flt(reconciled_entries[entry.voucher_type][entry.voucher_no]["rec_debit"]) <= \
								flt(reconciled_entries[entry.voucher_type][entry.voucher_no]["total_debit"]):
								rec_credit = flt(reconciled_entries[entry.voucher_type][entry.voucher_no]["rec_credit"])
								rec_debit = flt(reconciled_entries[entry.voucher_type][entry.voucher_no]["rec_debit"])

								debit = min(entry.debit, entry.cb_credit - rec_debit)
								credit = min(entry.credit, entry.cb_debit - rec_credit)
								d[period.key] = d.get(period.key, 0.0) + flt(debit) - flt(credit)

								reconciled_entries[entry.voucher_type][entry.voucher_no]["rec_credit"] = rec_credit + flt(credit)
								reconciled_entries[entry.voucher_type][entry.voucher_no]["rec_debit"] = rec_debit + flt(debit)

							else:
								continue

						else:
							debit = min(entry.debit, entry.cb_credit) if "cb_credit" in entry else entry.debit
							credit = min(entry.credit, entry.cb_debit) if "cb_debit" in entry else entry.credit
							d[period.key] = d.get(period.key, 0.0) + flt(debit) - flt(credit)

def add_to_reconciled_data(reconciled_entries, entry):
	if entry.voucher_no in reconciled_entries[entry.voucher_type]:
		total_credit = flt(reconciled_entries[entry.voucher_type][entry.voucher_no]["total_credit"]) + flt(entry.credit)
		total_debit = flt(reconciled_entries[entry.voucher_type][entry.voucher_no]["total_debit"]) + flt(entry.debit)
	else:
		total_credit = flt(entry.credit)
		total_debit = flt(entry.debit)
		reconciled_entries[entry.voucher_type][entry.voucher_no]["rec_credit"] = 0
		reconciled_entries[entry.voucher_type][entry.voucher_no]["rec_debit"] = 0

	reconciled_entries[entry.voucher_type][entry.voucher_no]["total_credit"] = total_credit
	reconciled_entries[entry.voucher_type][entry.voucher_no]["total_debit"] = total_debit

	return reconciled_entries

def get_unreconciled_amount(unreconciled, period_list, company, currency=None, consolidated=False):
	total = 0
	unreconciled_amount = {
		"account_name": "'" + _("Unreconcilied Balance") + "'",
		"account": "'" + _("Unreconcilied Balance") + "'",
		"warn_if_negative": False,
		"currency": currency or frappe.get_cached_value('Company',  company,  "default_currency"),
	}

	has_value = False

	for period in period_list:
		key = period if consolidated else period.key
		unreconciled_amount[key] = 0

		for dummy, value in iteritems(unreconciled):
			if value.get(key):
				unreconciled_amount[key] += flt(value.get(key))
				total += flt(value.get(key))
				has_value = True

	unreconciled_amount["total"] = total

	if has_value:
		return unreconciled_amount

def merge_similar_entries(gl_map, merge=False):
	merged_gl_map = []
	for entry in gl_map:
		# if there is already an entry in this account then just add it
		# to that entry
		same_head = check_if_in_list(entry, merged_gl_map, merge)
		if same_head and not merge:
			same_head["debit"]	= flt(same_head["debit"]) + flt(entry["debit"])
			same_head["credit"] = flt(same_head["credit"]) + flt(entry["credit"])
		elif same_head and merge:
			same_head["debit"] = flt(entry["debit"])
			same_head["credit"] = flt(entry["credit"])
			same_head["cb_debit"] = flt(same_head["cb_debit"]) + flt(entry["cb_debit"])
			same_head["cb_credit"] = flt(same_head["cb_credit"]) + flt(entry["cb_credit"])
		else:
			merged_gl_map.append(entry)

	if not merge:
		for merged_map in merged_gl_map:
			if merged_map["debit"] > 0 and merged_map["credit"]:
				total_debit = flt(merged_map["debit"]) - flt(merged_map["credit"])
				total_credit = flt(merged_map["credit"]) - flt(merged_map["debit"])
				merged_map["debit"] = total_debit if total_debit > 0 else 0
				merged_map["credit"] = total_credit if total_credit > 0 else 0
	# filter zero debit and credit entries
	merged_gl_map = filter(lambda x: flt(x["debit"], 9)!=0 or flt(x["credit"], 9)!=0, merged_gl_map)
	merged_gl_map = list(merged_gl_map)

	return merged_gl_map

def check_if_in_list(gle, gl_map, merge):
	for e in gl_map:
		if merge:
			if e["name"] == gle["name"] and e["voucher_type"] == gle["voucher_type"] \
				and e["voucher_no"] == gle["voucher_no"]:
				return e
		else:
			if e["account"] == gle["account"] and e["voucher_type"] == gle["voucher_type"] \
				and e["voucher_no"] == gle["voucher_no"]:
				return e