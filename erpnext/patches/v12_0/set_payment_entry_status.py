import frappe

def execute():
	frappe.db.sql("""update `tabPayment Entry` set status = CASE
		WHEN docstatus = 1 AND unreconciled_amount = 0 THEN 'Reconciled'
        WHEN docstatus = 1 AND unreconciled_amount > 0 THEN 'Unreconciled'
		WHEN docstatus = 2 THEN 'Cancelled'
		ELSE 'Draft'
		END;""")