# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import io
import re
import zipfile

import frappe
from frappe import _
from frappe.utils import cstr, format_date, format_datetime, get_datetime, sbool


def execute(filters=None):
	account_details = {}
	for acc in frappe.db.sql("""select name, is_group from tabAccount""", as_dict=1):
		account_details.setdefault(acc.name, acc)

	validate_filters(filters, account_details)

	filters = set_account_currency(filters)

	columns = get_columns(filters)

	res = get_result(filters)

	return columns, res


def validate_filters(filters, account_details):
	if not filters.get("company"):
		frappe.throw(_("{0} is mandatory").format(_("Company")))

	if not filters.get("fiscal_year"):
		frappe.throw(_("{0} is mandatory").format(_("Fiscal Year")))


def set_account_currency(filters):

	filters["company_currency"] = frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)

	return filters


def get_columns(filters):
	columns = [
		{"label": "JournalCode", "fieldname": "JournalCode", "width": 90},
		{"label": "JournalLib", "fieldname": "JournalLib", "width": 90},
		{"label": "EcritureNum", "fieldname": "EcritureNum", "width": 90},
		{"label": "EcritureDate", "fieldname": "EcritureDate", "width": 90},
		{"label": "CompteNum", "fieldname": "CompteNum", "width": 90},
		{"label": "CompteLib", "fieldname": "CompteLib", "width": 90},
		{"label": "CompAuxNum", "fieldname": "CompAuxNum", "width": 100},
		{"label": "CompAuxLib", "fieldname": "CompAuxLib", "width": 200},
		{"label": "PieceRefType", "fieldname": "PieceRefType", "width": 90, "hidden": 1},
		{
			"label": "PieceRef",
			"fieldname": "PieceRef",
			"width": 90,
			"fieldtype": "Dynamic Link",
			"options": "PieceRefType",
		},
		{"label": "PieceDate", "fieldname": "PieceDate", "width": 90},
		{"label": "EcritureLib", "fieldname": "EcritureLib", "width": 90},
		{"label": "Debit", "fieldname": "Debit", "width": 90},
		{"label": "Credit", "fieldname": "Credit", "width": 90},
		{"label": "EcritureLet", "fieldname": "EcritureLet", "width": 90},
		{"label": "DateLet", "fieldname": "DateLet", "width": 90},
		{"label": "ValidDate", "fieldname": "ValidDate", "width": 90},
		{"label": "Montantdevise", "fieldname": "Montantdevise", "width": 90},
		{"label": "Idevise", "fieldname": "Idevise", "width": 90},
	]

	return columns


def get_result(filters):
	gl_entries = get_gl_entries(filters)

	result = get_result_as_list(gl_entries, filters)

	return result


def get_gl_entries(filters):

	group_by_condition = (
		"group by voucher_type, voucher_no, account"
		if filters.get("group_by_voucher")
		else "group by gl.name"
	)

	gl_entries = frappe.db.sql(
		"""
		select
			gl.posting_date as GlPostDate, gl.name as GlName, gl.account, gl.transaction_date,
			sum(gl.debit) as debit, sum(gl.credit) as credit, gl.accounting_entry_number,
			sum(gl.debit_in_account_currency) as debitCurr, sum(gl.credit_in_account_currency) as creditCurr,
			gl.voucher_type, gl.voucher_no, gl.against_voucher_type,
			gl.against_voucher, gl.account_currency, gl.against,
			gl.party_type, gl.party, gl.accounting_journal, gl.remarks,
			inv.name as InvName, inv.title as InvTitle, inv.posting_date as InvPostDate,
			pur.name as PurName, pur.title as PurTitle, pur.posting_date as PurPostDate,
			jnl.cheque_no as JnlRef, jnl.posting_date as JnlPostDate, jnl.title as JnlTitle,
			pay.name as PayName, pay.posting_date as PayPostDate, pay.title as PayTitle,
			cus.customer_name, cus.name as cusName,
			sup.supplier_name, sup.name as supName,
			emp.employee_name, emp.name as empName

		from `tabGL Entry` gl
			left join `tabSales Invoice` inv on gl.voucher_no = inv.name
			left join `tabPurchase Invoice` pur on gl.voucher_no = pur.name
			left join `tabJournal Entry` jnl on gl.voucher_no = jnl.name
			left join `tabPayment Entry` pay on gl.voucher_no = pay.name
			left join `tabCustomer` cus on gl.party = cus.name
			left join `tabSupplier` sup on gl.party = sup.name
			left join `tabEmployee` emp on gl.party = emp.name
		where gl.company=%(company)s and gl.fiscal_year=%(fiscal_year)s
		{group_by_condition}
		order by GlPostDate, voucher_no""".format(
			group_by_condition=group_by_condition
		),
		filters,
		as_dict=1,
	)

	return gl_entries


def get_result_as_list(data, filters):
	result = []

	company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	accounts = frappe.get_all(
		"Account",
		filters={"Company": filters.company},
		fields=["name", "account_number", "account_name"],
	)
	journals = {
		j.journal_code: j.journal_name
		for j in frappe.get_all("Accounting Journal", fields=["journal_code", "journal_name"])
	}

	party_data = [x for x in data if x.get("against_voucher")]

	for d in data:
		JournalCode = d.get("accounting_journal") or re.split("-|/|[0-9]", d.get("voucher_no"))[0]
		EcritureNum = d.get("accounting_entry_number")

		EcritureDate = format_datetime(d.get("GlPostDate"), "yyyyMMdd")

		account_number = [
			{"account_number": account.account_number, "account_name": account.account_name}
			for account in accounts
			if account.name == d.get("account") and account.account_number
		]
		if account_number:
			CompteNum = account_number[0]["account_number"]
			CompteLib = account_number[0]["account_name"]
		else:
			frappe.throw(
				_(
					"Account number for account {0} is not available.<br> Please setup your Chart of Accounts correctly."
				).format(d.get("account"))
			)

		if d.get("party_type") == "Customer":
			CompAuxNum = d.get("cusName")
			CompAuxLib = d.get("customer_name")

		elif d.get("party_type") == "Supplier":
			CompAuxNum = d.get("supName")
			CompAuxLib = d.get("supplier_name")

		elif d.get("party_type") == "Employee":
			CompAuxNum = d.get("empName")
			CompAuxLib = d.get("employee_name")

		else:
			CompAuxNum = ""
			CompAuxLib = ""

		ValidDate = format_datetime(d.get("GlPostDate"), "yyyyMMdd")

		PieceRef = d.get("voucher_no") if d.get("voucher_no") else "Sans Reference"
		PieceRefType = d.get("voucher_type") or "Sans Reference"

		# EcritureLib is the reference title unless it is an opening entry
		if d.get("is_opening") == "Yes":
			EcritureLib = _("Opening Entry Journal")
		if d.get("remarks") and d.get("remarks").lower() not in ("no remarks", _("no remarks")):
			EcritureLib = d.get("remarks")
		elif d.get("voucher_type") == "Sales Invoice":
			EcritureLib = d.get("InvTitle")
		elif d.get("voucher_type") == "Purchase Invoice":
			EcritureLib = d.get("PurTitle")
		elif d.get("voucher_type") == "Journal Entry":
			EcritureLib = d.get("JnlTitle")
		elif d.get("voucher_type") == "Payment Entry":
			EcritureLib = d.get("PayTitle")
		else:
			EcritureLib = d.get("voucher_type")

		EcritureLib = EcritureLib.replace("\n", " ")

		PieceDate = format_datetime(d.get("GlPostDate"), "yyyyMMdd")

		debit = "{:.2f}".format(d.get("debit")).replace(".", ",")

		credit = "{:.2f}".format(d.get("credit")).replace(".", ",")

		Idevise = d.get("account_currency")

		DateLet = get_date_let(d, party_data) if d.get("against_voucher") else None
		EcritureLet = d.get("against_voucher", "") if DateLet else ""

		Montantdevise = None
		if Idevise != company_currency:
			Montantdevise = (
				"{:.2f}".format(d.get("debitCurr")).replace(".", ",")
				if d.get("debitCurr") != 0
				else "{:.2f}".format(d.get("creditCurr")).replace(".", ",")
			)

		row = {
			"JournalCode": JournalCode,
			"JournalLib": journals.get(JournalCode),
			"EcritureNum": EcritureNum,
			"EcritureDate": EcritureDate,
			"CompteNum": CompteNum,
			"CompteLib": CompteLib,
			"CompAuxNum": CompAuxNum,
			"CompAuxLib": CompAuxLib,
			"PieceRefType": PieceRefType,
			"PieceRef": PieceRef,
			"PieceDate": PieceDate,
			"EcritureLib": EcritureLib,
			"Debit": debit,
			"Credit": credit,
			"EcritureLet": EcritureLet,
			"DateLet": DateLet or "",
			"ValidDate": ValidDate,
			"Montantdevise": Montantdevise,
			"Idevise": Idevise if Idevise != company_currency else None,
		}

		result.append(row)

	return result


def get_date_let(d, data):
	let_dates = [
		x.get("GlPostDate")
		for x in data
		if (
			x.get("against_voucher") == d.get("against_voucher")
			and x.get("against_voucher_type") == d.get("against_voucher_type")
			and x.get("party") == d.get("party")
		)
	]

	if not let_dates or len(let_dates) == 1:
		let_vouchers = frappe.get_all(
			"GL Entry",
			filters={
				"against_voucher": d.get("against_voucher"),
				"against_voucher_type": d.get("against_voucher_type"),
				"party": d.get("party"),
			},
			fields=["posting_date"],
		)

		if len(let_vouchers) > 1:
			return format_datetime(max([x.get("posting_date") for x in let_vouchers]), "yyyyMMdd")

	return format_datetime(max(let_dates), "yyyyMMdd") if len(let_dates) > 1 else None


@frappe.whitelist()
def export_report(filters, with_files=False):
	from frappe.utils.csvutils import to_csv
	from PyPDF2 import PdfMerger, PdfReader

	filters = frappe._dict(frappe.parse_json(filters))
	with_files = sbool(with_files)

	siren = frappe.db.get_value("Company", filters.company, "siren_number")
	if not siren:
		frappe.msgprint(_("Please register the SIREN number in the company information file"))

	year_end_date = frappe.db.get_value("Fiscal Year", filters.fiscal_year, "year_end_date")
	title = f"{siren}FEC{format_date(year_end_date, 'YYYYMMdd')}"
	report = execute(filters=filters)
	if not report:
		return

	prepared_values = []
	header_row = []
	for header in report[0]:
		if header.get("fieldname") != "PieceRefType":
			header_row.append(header.get("label"))

	prepared_values.append(header_row)
	for line in report[1]:
		prepared_line = line.copy()
		prepared_line.pop("PieceRefType")
		prepared_values.append(prepared_line.values())

	fec_csv_file = cstr(to_csv(prepared_values, quoting="QUOTE_MINIMAL", delimiter="\t"))

	if not with_files:
		frappe.response["result"] = fec_csv_file
		frappe.response["doctype"] = title
		frappe.response["type"] = "txt"

	else:
		files = [{"file_name": f"{title}.txt", "content": fec_csv_file}]

		references_added = []
		for line in report[1]:
			if (
				line.get("PieceRef")
				and line.get("PieceRef") not in references_added
				and line.get("PieceRef") != "Sans Reference"
				and line.get("PieceRefType") in ["Sales Invoice", "Purchase Invoice", "Expense Claim"]
			):
				attached_files = frappe.get_all(
					"File",
					filters={
						"attached_to_doctype": line.get("PieceRefType"),
						"attached_to_name": line.get("PieceRef"),
					},
					fields=["name", "file_name", "file_url"],
				)

				merger = PdfMerger()
				for attached_file in attached_files:
					# if attached_file.file_name == "Facture_FR45923584.pdf":
					# 	print(line.get("PieceRef"), attached_file)
					if attached_file.file_name.endswith(".pdf"):
						filedoc = frappe.get_doc("File", attached_file.name)
						try:
							content = io.BytesIO(filedoc.get_content())
							merger.append(PdfReader(content))
						except Exception:
							continue

				if merger.pages:
					merged_pdf = io.BytesIO()
					merger.write(merged_pdf)

					merger.close()
					merged_pdf.seek(0)

					files.append({"file_name": f'{line.get("PieceRef")}.pdf', "content": merged_pdf.read()})

				references_added.append(line.get("PieceRef"))

		frappe.response["filename"] = f'FEC+Pieces_{get_datetime().strftime("%Y%m%d_%H%M%S")}.zip'
		frappe.response["filecontent"] = zip_files(files)
		frappe.response["type"] = "download"


def zip_files(files):
	zip_file = io.BytesIO()
	zf = zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED)
	for _file in files:
		zf.writestr(_file["file_name"], _file["content"])
	zf.close()
	return zip_file.getvalue()
