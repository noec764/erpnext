import unittest

import frappe
from frappe.utils import nowdate, flt

from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry

test_dependencies = ["Journal Entry", "Contact", "Address"]
test_records = frappe.get_test_records('Sales Invoice')

class TestDownPayment(unittest.TestCase):
	def setUp(self):
		frappe.db.set_value("Company", "_Test Company", "default_down_payment_receivable_account", "_Test Down Payment - _TC")

	def make(self, is_return=False, return_against=None):
		test_record = [r for r in test_records if r.get("title") == "Down Payment Invoice"]
		dp_invoice = frappe.copy_doc(test_record[0])
		dp_invoice.is_pos = 0
		if is_return:
			dp_invoice.is_return = True
			dp_invoice.return_against = return_against

			for item in dp_invoice.items:
				item.qty = item.qty * -1

		dp_invoice.insert()
		dp_invoice.submit()
		return dp_invoice

	def test_no_gl_entries(self):
		dp_invoice = self.make()
		self.assertTrue(dp_invoice.debit_to == "_Test Down Payment - _TC")
		self.assertTrue(flt(dp_invoice.outstanding_amount) == 500)

		gl_entries = frappe.get_all("GL Entry", filters={"voucher_type": "Sales Invoice", "voucher_no": dp_invoice.name})
		self.assertFalse(gl_entries)

	def test_outstanding_amount_for_advances(self):
		dp_invoice_1 = self.make()
		dp_invoice_2 = self.make()

		self.assertTrue(flt(dp_invoice_1.outstanding_amount) == 500)
		self.assertTrue(flt(dp_invoice_2.outstanding_amount) == 500)

		pe = get_payment_entry("Sales Invoice", dp_invoice_1.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = dp_invoice_1.currency
		pe.paid_to_account_currency = dp_invoice_1.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = dp_invoice_1.grand_total + dp_invoice_2.grand_total
		pe.received_amount = dp_invoice_1.grand_total + dp_invoice_2.grand_total

		pe.append("references", {
			"reference_doctype": "Sales Invoice",
			"reference_name": dp_invoice_2.name,
			"allocated_amount": dp_invoice_2.outstanding_amount
		})

		pe.insert()
		pe.submit()

		dp_invoice_1.reload()
		dp_invoice_2.reload()
		self.assertTrue(flt(dp_invoice_1.outstanding_amount) == 0)
		self.assertTrue(flt(dp_invoice_2.outstanding_amount) == 0)

		return_invoice = self.make(is_return=True, return_against=dp_invoice_2.name)
		self.assertTrue(flt(return_invoice.outstanding_amount) == 0)
		dp_invoice_2.reload()
		self.assertTrue(flt(dp_invoice_2.outstanding_amount) == -500)

	def test_outstanding_amount_for_payment_entries(self):
		dp_invoice = self.make()
		pe = get_payment_entry("Sales Invoice", dp_invoice.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = dp_invoice.currency
		pe.paid_to_account_currency = dp_invoice.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = dp_invoice.grand_total
		pe.insert()
		pe.submit()

		self.assertTrue(pe.paid_from == "_Test Down Payment - _TC")

		dp_invoice.reload()
		self.assertTrue(flt(dp_invoice.outstanding_amount) == 0)

	def test_outstanding_amount_for_credit_notes(self):
		dp_invoice = self.make()
		pe = get_payment_entry("Sales Invoice", dp_invoice.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = dp_invoice.currency
		pe.paid_to_account_currency = dp_invoice.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = dp_invoice.outstanding_amount
		pe.insert()
		pe.submit()

		dp_invoice.reload()
		self.assertTrue(flt(dp_invoice.outstanding_amount) == 0)

		return_invoice = self.make(is_return=True, return_against=dp_invoice.name)
		self.assertTrue(flt(return_invoice.outstanding_amount) == 0)

		dp_invoice.reload()
		self.assertTrue(flt(dp_invoice.outstanding_amount) == -500)

		pe = get_payment_entry("Sales Invoice", dp_invoice.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = dp_invoice.currency
		pe.paid_to_account_currency = dp_invoice.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = abs(dp_invoice.outstanding_amount)
		pe.received_amount = abs(dp_invoice.outstanding_amount)
		pe.insert()
		pe.submit()

		dp_invoice.reload()
		self.assertTrue(flt(dp_invoice.outstanding_amount) == 0)

	def test_gl_entries_for_final_invoice(self):
		dp_invoice = self.make()
		pe = get_payment_entry("Sales Invoice", dp_invoice.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = dp_invoice.currency
		pe.paid_to_account_currency = dp_invoice.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = abs(dp_invoice.outstanding_amount)
		pe.received_amount = abs(dp_invoice.outstanding_amount)
		pe.insert()
		pe.submit()

		gl = frappe.get_all("GL Entry", filters={"voucher_type": "Payment Entry", "voucher_no": pe.name}, fields=["is_cancelled", "debit", "credit", "account"])
		self.assertTrue(any(x.get("account") == "_Test Down Payment - _TC" for x in gl))
		self.assertTrue(not any(x for x in gl if x.is_cancelled == 1))

		final_invoice = frappe.copy_doc(dp_invoice)
		final_invoice.docstatus = 0
		final_invoice.is_down_payment_invoice = False
		final_invoice.items[0].item_code = "_Test Item"
		final_invoice.items[0].rate = 1000
		final_invoice.debit_to = "_Test Receivable - _TC"
		final_invoice.allocate_advances_automatically = 0
		final_invoice.insert()

		pe.reload()
		final_invoice.reload()
		final_invoice.append("advances", {
			"reference_type": "Payment Entry",
			"reference_name": pe.name,
			"reference_row": pe.references[0].name,
			"advance_amount": flt(500.0),
			"allocated_amount": flt(500.0)
		})
		final_invoice.save()
		final_invoice.submit()

		self.assertTrue(flt(final_invoice.outstanding_amount), 500)

		gl = frappe.get_all("GL Entry", filters={"voucher_type": "Payment Entry", "voucher_no": pe.name}, fields=["is_cancelled", "debit", "credit", "account"])
		self.assertTrue(not any(x.get("account") == "_Test Down Payment - _TC" for x in gl if x.is_cancelled == 0))
		self.assertTrue(any(x.get("account") == "_Test Receivable - _TC" for x in gl if x.is_cancelled == 0))
