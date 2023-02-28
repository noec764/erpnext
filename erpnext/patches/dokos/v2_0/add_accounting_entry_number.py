import frappe

from erpnext.accounts.general_ledger import get_accounting_number


def execute():
	frappe.reload_doc("accounts", "doctype", "GL Entry")
	vouchers = {}
	for gl in frappe.get_all(
		"GL Entry",
		filters={"accounting_entry_number": ("is", "not set")},
		order_by="posting_date, voucher_no asc",
		fields=["posting_date", "voucher_no", "name", "fiscal_year"],
	):
		if gl.voucher_no not in vouchers:
			vouchers[gl.voucher_no] = get_accounting_number(gl)
		frappe.db.set_value("GL Entry", gl.name, "accounting_entry_number", vouchers[gl.voucher_no])
