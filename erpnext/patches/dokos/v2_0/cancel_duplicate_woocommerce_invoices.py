import frappe

from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.controllers.sales_and_purchase_return import make_return_doc


def execute():
	if not frappe.get_meta("Sales Order").has_field("woocommerce_id"):
		return

	for sales_order in frappe.get_all(
		"Sales Order", filters={"woocommerce_id": ("is", "set"), "docstatus": 1}
	):
		sales_invoices = list(
			set(
				x[0]
				for x in frappe.db.sql(
					f"""
			select
				si.name
			from
				`tabSales Invoice` si, `tabSales Invoice Item` si_item
			where
				si.name = si_item.parent
				and si_item.sales_order = {frappe.db.escape(sales_order.name)}
				and si.docstatus = 1
				and not si.is_return = 1
		""",
					as_list=True,
				)
			)
		)

		if len(sales_invoices) > 1:
			try:
				doc = make_return_doc("Sales Invoice", max(sales_invoices))
				doc.insert()
				doc.submit()

				pe = get_payment_entry("Sales Invoice", max(sales_invoices))
				pe.reference_no = doc.name
				pe.reference_date = pe.posting_date
				if pe.paid_amount > 0:
					pe.insert()
					pe.submit()
			except Exception:
				print(
					f"A error preventing creating a credit note for sales invoice n°{max(sales_invoices)}. Please create it manually."
				)
