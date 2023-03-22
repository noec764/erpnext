import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry
from erpnext.setup.utils import get_exchange_rate

test_dependencies = ["Journal Entry", "Contact", "Address", "Account"]
test_records = frappe.get_test_records("Sales Invoice")


class TestDownPayment(FrappeTestCase):
	def setUp(self):
		frappe.db.set_value(
			"Company",
			"_Test Company",
			"default_down_payment_receivable_account",
			"_Test Down Payment - _TC",
		)

	def make(self, is_return=False, return_against=None):
		test_record = [r for r in test_records if r.get("title") == "Down Payment Invoice"]
		dp_invoice = frappe.copy_doc(test_record[0])
		dp_invoice.is_pos = 0
		dp_invoice.is_down_payment_invoice = 1
		if is_return:
			dp_invoice.is_return = True
			dp_invoice.return_against = return_against

			for item in dp_invoice.items:
				item.qty = item.qty * -1

		dp_invoice.insert()
		dp_invoice.submit()
		return dp_invoice

	def test_down_payment_gl_entries(self):
		dp_invoice = self.make()
		self.assertTrue(dp_invoice.items[0].income_account == "_Test Down Payment - _TC")
		self.assertTrue(flt(dp_invoice.outstanding_amount) == 500)

		gl_entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Sales Invoice", "voucher_no": dp_invoice.name},
			pluck="account",
		)
		self.assertListEqual(gl_entries, ["_Test Down Payment - _TC", "_Test Receivable - _TC"])

	def test_outstanding_amount_for_advances(self):
		dp_invoice_1 = self.make()
		dp_invoice_2 = self.make()

		self.assertTrue(flt(dp_invoice_1.outstanding_amount) == 500.0)
		self.assertTrue(flt(dp_invoice_2.outstanding_amount) == 500.0)

		pe = get_payment_entry("Sales Invoice", dp_invoice_1.name, bank_account="_Test Bank - _TC")
		pe.reference_no = "1"
		pe.reference_date = nowdate()
		pe.paid_from_account_currency = dp_invoice_1.currency
		pe.paid_to_account_currency = dp_invoice_1.currency
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = dp_invoice_1.grand_total + dp_invoice_2.grand_total
		pe.received_amount = dp_invoice_1.grand_total + dp_invoice_2.grand_total

		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": dp_invoice_2.name,
				"allocated_amount": dp_invoice_2.outstanding_amount,
			},
		)

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

		self.assertTrue(pe.paid_from == "_Test Receivable - _TC")

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

		gl = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Payment Entry", "voucher_no": pe.name},
			fields=["is_cancelled", "debit", "credit", "account"],
		)
		self.assertTrue(not any(x for x in gl if x.is_cancelled == 1))

		final_invoice = frappe.copy_doc(dp_invoice)
		final_invoice.docstatus = 0
		final_invoice.is_down_payment_invoice = False
		final_invoice.items[0].item_code = "_Test Item"
		final_invoice.items[0].income_account = "Sales - _TC"
		final_invoice.items[0].rate = 1000
		final_invoice.debit_to = "_Test Receivable - _TC"
		final_invoice.allocate_advances_automatically = 0
		final_invoice.insert()

		pe.reload()
		final_invoice.reload()
		final_invoice.append(
			"advances",
			{
				"reference_type": "Payment Entry",
				"reference_name": pe.name,
				"reference_row": pe.references[0].name,
				"advance_amount": flt(500.0),
				"allocated_amount": flt(500.0),
				"is_down_payment": 1,
			},
		)
		final_invoice.save()
		final_invoice.submit()

		self.assertTrue(flt(final_invoice.outstanding_amount), 500)

		gl = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Payment Entry", "voucher_no": pe.name},
			fields=["is_cancelled", "debit", "credit", "account"],
		)
		self.assertTrue(
			not any(x.get("account") == "_Test Down Payment - _TC" for x in gl if x.is_cancelled == 0)
		)
		self.assertTrue(
			any(x.get("account") == "_Test Receivable - _TC" for x in gl if x.is_cancelled == 0)
		)


class TestDownPaymentMultiplePayments(FrappeTestCase):
	def setUp(self):
		frappe.db.set_value(
			"Company",
			"_Test Company",
			"default_down_payment_receivable_account",
			"_Test Down Payment USD - _TC",
		)

	def get_accounting_params(self):
		return {
			"company": "_Test Company",
			"cost_center": "_Test Cost Center - _TC",
			"warehouse": "_Test Warehouse - _TC",
			"currency": "USD",
			"party_account_currency": "USD",
			"price_list_currency": "USD",
			"selling_price_list": "Standard Selling",
			"conversion_rate": get_exchange_rate("USD", "INR"),
		}

	def create_sales_order(self, amount: float):
		return frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": "_Test Customer USD",
				**self.get_accounting_params(),
				"items": [
					{
						**self.get_accounting_params(),
						"item_code": "_Test Item",
						"qty": 1,
						"rate": amount,
						"delivery_date": "2020-01-01",
					}
				],
				"taxes_and_charges": "",
			}
		)

	def create_sales_invoice(self, sales_order: "frappe.Document"):
		return frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": sales_order.customer,
				**self.get_accounting_params(),
				"items": [
					{
						**self.get_accounting_params(),
						**item.as_dict(),
						"name": None,
						"parent": None,
						"parentfield": None,
						"parenttype": None,
						"idx": None,
						"doctype": "Sales Invoice Item",
						"sales_order": sales_order.name,
					}
					for item in sales_order.items
				],
				"taxes_and_charges": "",
				"is_down_payment_invoice": 0,
				"is_pos": 0,
				"disable_rounded_total": 0,
			}
		)

	def create_down_payment_sales_invoice(
		self, sales_order: "frappe.Document", percentage: float = 0.3
	):
		return frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": sales_order.customer,
				**self.get_accounting_params(),
				"items": [
					{
						**self.get_accounting_params(),
						"doctype": "Sales Invoice Item",
						"item_code": "999-Down Payment",
						"qty": 1,
						"rate": sales_order.grand_total * percentage,
						"delivery_date": "2020-01-01",
						"sales_order": sales_order.name,
					}
				],
				"taxes_and_charges": "",
				"is_down_payment_invoice": 1,
				"is_pos": 0,
				"disable_rounded_total": 0,
			}
		)

	def create_payment_entry(self, voucher: "frappe.Document", amount: float):
		return frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"company": voucher.company,
				"payment_type": "Receive",
				"party_type": "Customer",
				"party": voucher.customer,
				"paid_from": "_Test Receivable USD - _TC",
				"paid_to": "_Test Bank USD - _TC",
				"paid_from_account_currency": "USD",
				"paid_to_account_currency": "USD",
				"paid_amount": amount,
				"received_amount": amount,
				"reference_no": "123",
				"reference_date": "2020-01-01",
				"references": [
					{
						"reference_doctype": voucher.doctype,
						"reference_name": voucher.name,
						"allocated_amount": amount,
						"due_date": "2020-01-01",
					}
				],
			}
		)

	def get_advance_for_payment_entry(self, pe: "frappe.Document"):
		return {
			"reference_name": pe.name,
			"reference_type": "Payment Entry",
			"advance_amount": pe.paid_amount,
			"allocated_amount": pe.paid_amount,
			"is_down_payment": 1,
			"ref_exchange_rate": self.get_accounting_params()["conversion_rate"],
		}

	def test_down_payment_full(self):
		# Create a Sales Order
		so = self.create_sales_order(amount=10_000)
		so.submit().reload()

		self.assertAlmostEqual(so.grand_total, 10_000)
		self.assertAlmostEqual(so.total_taxes_and_charges, 0)
		self.assertEqual(len(so.taxes), 0)

		# Create a down payment Sales Invoice against the Sales Order
		dp_si = self.create_down_payment_sales_invoice(sales_order=so, percentage=0.3)
		dp_si.submit().reload()

		self.assertAlmostEqual(dp_si.grand_total, 3_000)
		self.assertAlmostEqual(dp_si.total_advance, 0)
		self.assertAlmostEqual(dp_si.outstanding_amount, 3_000)
		self.assertAlmostEqual(dp_si.total_taxes_and_charges, 0)
		self.assertEqual(len(dp_si.taxes), 0)

		# Create a Payment Entry against the Sales Invoice
		advances = []
		for v in [100, 900, 2000]:
			pe = self.create_payment_entry(voucher=dp_si, amount=v)
			pe.submit().reload()
			advances.append(pe)

		# Create a draft Sales Invoice against the Sales Order, and add the payments as advances
		si = self.create_sales_invoice(sales_order=so)
		for dp in advances:
			si.append("advances", self.get_advance_for_payment_entry(pe=dp))

		si.save().reload()

		self.assertAlmostEqual(si.grand_total, 10_000)
		self.assertAlmostEqual(si.total_advance, 3_000)
		self.assertAlmostEqual(si.outstanding_amount, 7000)

		# Submit the Sales Invoice
		si.submit().reload()

		self.assertAlmostEqual(si.grand_total, 10_000)
		self.assertAlmostEqual(si.total_advance, 3_000)
		self.assertAlmostEqual(si.outstanding_amount, 7_000)
		self.assertEqual(si.status, "Partly Paid")

		dp_si.reload()
		self.assertEqual(dp_si.status, "Paid")

	def test_down_payment_partial(self):
		so = self.create_sales_order(amount=10_000).submit()
		dp_si = self.create_down_payment_sales_invoice(sales_order=so, percentage=0.3)
		dp_si.submit()

		advances = []
		for v in [10, 90]:
			advances.append(self.create_payment_entry(voucher=dp_si, amount=v).submit())

		si = self.create_sales_invoice(sales_order=so)
		for dp in advances:
			si.append("advances", self.get_advance_for_payment_entry(pe=dp))

		si.save()

		self.assertAlmostEqual(si.grand_total, 10_000)
		self.assertAlmostEqual(si.total_advance, 100)
		self.assertAlmostEqual(si.outstanding_amount, 9_900)

		si.submit().reload()

		self.assertAlmostEqual(si.grand_total, 10_000)
		self.assertAlmostEqual(si.total_advance, 100)
		# The outstanding amount of the invoice is the grand total (10_000) minus the down payment (3000, 30% of 10_000), which is 7_000
		self.assertAlmostEqual(si.outstanding_amount, 7_000)
		self.assertEqual(si.status, "Partly Paid")

		dp_si.reload()
		self.assertEqual(dp_si.outstanding_amount, 3000 - 100)
		self.assertEqual(dp_si.status, "Partly Paid")

	def test_down_payment_partial_two_decimal_places(self):
		so = self.create_sales_order(amount=10_000.50).submit()
		dp_si = self.create_down_payment_sales_invoice(sales_order=so, percentage=0.3)
		dp_si.submit()

		advances = []
		for v in [10, 90]:
			advances.append(self.create_payment_entry(voucher=dp_si, amount=v).submit())

		si = self.create_sales_invoice(sales_order=so)
		for dp in advances:
			si.append("advances", self.get_advance_for_payment_entry(pe=dp))

		si.save()

		self.assertAlmostEqual(si.grand_total, 10_000.50)
		self.assertAlmostEqual(si.total_advance, 100)
		self.assertAlmostEqual(si.outstanding_amount, 9_900.50)

		si.submit().reload()

		self.assertAlmostEqual(si.grand_total, 10_000.50)
		self.assertAlmostEqual(si.total_advance, 100)
		# The outstanding amount of the invoice is the grand total (10_000.50) minus the down payment (3000.15, 30% of 10_000.50), which is 7_000.35
		self.assertAlmostEqual(si.outstanding_amount, 7_000.35)
		self.assertEqual(si.status, "Partly Paid")

		dp_si.reload()
		self.assertEqual(dp_si.outstanding_amount, 3000.15 - 100)
		self.assertEqual(dp_si.status, "Partly Paid")

	@unittest.skip(
		"Not working yet because rounding is not supported for outstanding amount: si.precision('outstanding_amount') is 2."
	)
	def test_down_payment_not_rounded(self):
		so = self.create_sales_order(amount=10_000.410)
		so.disable_rounded_total = 1
		so.submit()

		dp_si = self.create_down_payment_sales_invoice(sales_order=so, percentage=0.3)
		dp_si.disable_rounded_total = 1
		dp_si.submit()

		advances = []
		for v in [10, 90]:
			advances.append(self.create_payment_entry(voucher=dp_si, amount=v).submit())

		si = self.create_sales_invoice(sales_order=so)
		si.disable_rounded_total = 1
		for dp in advances:
			si.append("advances", self.get_advance_for_payment_entry(pe=dp))

		si.save()

		self.assertAlmostEqual(si.grand_total, 10_000.410)
		self.assertAlmostEqual(si.total_advance, 100)
		self.assertAlmostEqual(si.outstanding_amount, 9_900.410)

		si.submit().reload()

		self.assertAlmostEqual(si.grand_total, 10_000.410)
		self.assertAlmostEqual(si.total_advance, 100)
		# The outstanding amount of the invoice is the grand total (10_000.410) minus the down payment (3000.123, 30% of 10_000.410), which is 7_000.287
		self.assertAlmostEqual(
			si.outstanding_amount, 7_000.287
		)  # TODO: This is failing because of rounding: got 7_000.29
		self.assertEqual(si.status, "Partly Paid")

		dp_si.reload()
		self.assertEqual(dp_si.status, "Partly Paid")
