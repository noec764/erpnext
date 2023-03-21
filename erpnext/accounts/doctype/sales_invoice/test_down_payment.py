import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from erpnext.accounts.doctype.payment_entry.test_payment_entry import get_payment_entry

test_dependencies = ["Journal Entry", "Contact", "Address"]
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


class TestDownPayment2(FrappeTestCase):
	def setUp(self):
		frappe.db.set_value(
			"Company",
			"_Test Company",
			"default_down_payment_receivable_account",
			"_Test Down Payment - _TC",
		)

	def get_accounting_params(self):
		return {
			"company": "_Test Company",
			"cost_center": "_Test Cost Center - _TC",
			"warehouse": "_Test Warehouse - _TC",
			"currency": "INR",
			"selling_price_list": "Standard Selling",
		}

	def create_sales_order(self, amount: float):
		return frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": "_Test Customer",
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
				"paid_from": "Debtors - _TC",
				"paid_to": "Cash - _TC",
				"paid_amount": amount,
				"received_amount": amount,
				"reference_no": "123",
				"reference_date": "2020-01-01",
				"references": [
					{
						"reference_doctype": voucher.doctype,
						"reference_name": voucher.name,
						"allocated_amount": amount,
					}
				],
			}
		)

	def test_down_payment_full(self):
		# Create a Sales Order
		so = self.create_sales_order(amount=10000)
		so.submit().reload()

		self.assertEqual(so.grand_total, 10000)
		self.assertEqual(so.total_taxes_and_charges, 0)
		self.assertEqual(len(so.taxes), 0)

		# Create a down payment Sales Invoice against the Sales Order
		dp_si = self.create_down_payment_sales_invoice(sales_order=so, percentage=0.3)
		dp_si.submit().reload()

		self.assertEqual(dp_si.grand_total, 3000)
		self.assertEqual(dp_si.total_advance, 0)
		self.assertEqual(dp_si.outstanding_amount, 3000)
		self.assertEqual(dp_si.total_taxes_and_charges, 0)
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
			si.append(
				"advances",
				{
					"reference_name": dp.name,
					"reference_type": "Payment Entry",
					"advance_amount": dp.paid_amount,
					"allocated_amount": dp.paid_amount,
					"is_down_payment": 1,
				},
			)

		si.save().reload()

		self.assertEqual(si.grand_total, 10000)
		self.assertEqual(si.total_advance, 3000)
		self.assertEqual(si.outstanding_amount, 7000)

		# Submit the Sales Invoice
		si.submit().reload()

		self.assertEqual(si.grand_total, 10000)
		self.assertEqual(si.total_advance, 3000)
		self.assertEqual(si.outstanding_amount, si.grand_total - si.total_advance)
		self.assertEqual(si.status, "Partly Paid")

	def test_down_payment_partial(self):
		so = self.create_sales_order(amount=10000).submit()
		dp_si = self.create_down_payment_sales_invoice(sales_order=so, percentage=0.3).submit()

		advances = []
		for v in [100, 900]:
			advances.append(self.create_payment_entry(voucher=dp_si, amount=v).submit())

		si = self.create_sales_invoice(sales_order=so)
		for dp in advances:
			si.append(
				"advances",
				{
					"reference_name": dp.name,
					"reference_type": "Payment Entry",
					"advance_amount": dp.paid_amount,
					"allocated_amount": dp.paid_amount,
					"is_down_payment": 1,
				},
			)

		si.save()

		self.assertEqual(si.grand_total, 10000)
		self.assertEqual(si.total_advance, 1000)
		self.assertEqual(si.outstanding_amount, si.grand_total - si.total_advance)

		si.submit().reload()
		self.assertEqual(si.grand_total, 10000)
		self.assertEqual(si.total_advance, 1000)
		self.assertEqual(si.outstanding_amount, si.grand_total - si.total_advance)
		self.assertEqual(si.status, "Partly Paid")
