import unittest

import frappe

test_records = frappe.get_test_records('Sales Invoice')

class TestDownPayment(unittest.TestCase):
	def make(self):
		test_record = [r for r in test_records if r["title"] == "Down Payment Invoice"]
		w = frappe.copy_doc(test_record)
		w.is_pos = 0
		w.insert()
		w.submit()
		return w


	def test_no_gl_entries(self):
		pass

	def test_outstanding_amount_for_advances(self):
		pass

	def test_outstanding_amount_for_payment_entries(self):
		pass

	def test_outstanding_amount_for_credit_notes(self):
		pass

	def test_gl_entries_for_payment_entry(self):
		pass

	def test_gl_entries_for_final_invoice(self):
		pass
