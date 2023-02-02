import unittest
import frappe
from frappe.tests.utils import FrappeTestCase, change_settings
from contextlib import contextmanager

from erpnext.e_commerce.doctype.website_item.website_item import make_website_item
from erpnext.e_commerce.shopping_cart.cart import (
	_get_cart_quotation,
	update_cart,
	get_shopping_cart_settings,
	get_debtors_account,
)

from erpnext.venue.doctype.venue_settings.venue_settings import MULTICOMPANY_COOKIE_NAME, MULTICOMPANY_FLAG_NAME


# Utility functions

@contextmanager
def with_cookies(cookies):
	"""Context manager to set cookies in the request"""
	from frappe.auth import CookieManager
	from types import SimpleNamespace

	original_object = frappe.local.cookie_manager if hasattr(frappe.local, "cookie_manager") else None
	original_request = frappe.request

	frappe.local.cookie_manager = CookieManager()
	frappe.request = SimpleNamespace(cookies=cookies)
	for key, value in cookies.items():
		frappe.local.cookie_manager.set_cookie(key, value, expires=365)

	yield

	frappe.local.cookie_manager = original_object
	frappe.request = original_request

@contextmanager
def with_user(user):
	"""Context manager to set user in the request"""
	original_user = frappe.session.user if frappe.session else None
	frappe.set_user(user)
	yield
	frappe.set_user(original_user)


# References to mock data (only INR currency)

DEFAULT_COMPANY = '_Test Company with perpetual inventory'
DEFAULT_PRICE_LIST = '_Test Price List India'
OVERRIDDEN_PRICE_LIST = '_Test Price List India'

ALT_COMPANY_1 = '_Test Company'
ALT_PRICE_LIST_1 = '_Test Price List'

ALT_COMPANY_2 = '_Test Company 3'
ALT_PRICE_LIST_2 = '_Test Price List 2'

TEST_ITEM_1 = {
	'item_code': '_Test Item',
	'only_companies': [DEFAULT_COMPANY, ALT_COMPANY_1],
}
TEST_ITEM_2 = {
	'item_code': '_Test Item 2',
	'only_companies': [DEFAULT_COMPANY, ALT_COMPANY_2],
}
TEST_ITEM_ALL = {
	'item_code': '_Test Item With Item Tax Template',
	'only_companies': [DEFAULT_COMPANY, ALT_COMPANY_1, ALT_COMPANY_2],
}

TEST_USER = 'test@example.com'

class BaseTestVenueCartSettings(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()  # note: call super first for rollback to work
		frappe.set_user("Administrator")

		e_commerce_settings = frappe.get_single("E Commerce Settings")
		e_commerce_settings.update({
			"enabled": 1,
			"company": DEFAULT_COMPANY,
			"price_list": DEFAULT_PRICE_LIST,
			"default_customer_group": "_Test Customer Group",
			"enable_checkout": 1,
			"no_payment_gateway": 1,
		})
		e_commerce_settings.save()

		venue = frappe.get_single("Venue Settings")
		venue.enable_multi_companies = True

		# NOTE: The overrides are cached for the full runtime.
		venue.cart_settings_overrides = []  # do not forget to clear the list
		venue.append('cart_settings_overrides', {
			'company': DEFAULT_COMPANY,
			'price_list': OVERRIDDEN_PRICE_LIST,  # override the default price list
		})
		venue.append('cart_settings_overrides', {
			'company': ALT_COMPANY_1,
			'price_list': ALT_PRICE_LIST_1,
		})
		venue.append('cart_settings_overrides', {
			'company': ALT_COMPANY_2,
			'price_list': ALT_PRICE_LIST_2,
		})

		venue.save()

	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if MULTICOMPANY_FLAG_NAME in frappe.flags:
			del frappe.flags[MULTICOMPANY_FLAG_NAME]  # reset the flag


class TestVenueCartSettings(BaseTestVenueCartSettings):
	def assertShoppingCartSettings(self, expected: dict):
		self.assertDocumentEqual(expected, get_shopping_cart_settings())

	@change_settings('Venue Settings', {'enable_multi_companies': False})
	@with_cookies({})  # no cookie
	def test_no_override_if_disabled(self):
		self.assertShoppingCartSettings({ 'price_list': DEFAULT_PRICE_LIST })

	@change_settings('Venue Settings', {'enable_multi_companies': False})
	@with_cookies({ MULTICOMPANY_COOKIE_NAME: ALT_COMPANY_1 })
	def test_no_override_if_disabled_even_with_cookie(self):
		self.assertShoppingCartSettings({ 'price_list': DEFAULT_PRICE_LIST })

	@with_cookies({})  # no cookie
	def test_no_override_if_enabled_even_without_cookie(self):
		self.assertShoppingCartSettings({ 'price_list': DEFAULT_PRICE_LIST })

	@with_cookies({ MULTICOMPANY_COOKIE_NAME: ALT_COMPANY_1 })
	def test_override_if_cookie1(self):
		self.assertShoppingCartSettings({ 'price_list': ALT_PRICE_LIST_1 })

	@with_cookies({ MULTICOMPANY_COOKIE_NAME: ALT_COMPANY_2 })
	def test_override_if_cookie2(self):
		self.assertShoppingCartSettings({ 'price_list': ALT_PRICE_LIST_2 })

	@with_cookies({ MULTICOMPANY_COOKIE_NAME: DEFAULT_COMPANY })
	def test_override_even_if_same_name_as_default_company(self):
		self.assertShoppingCartSettings({ 'price_list': OVERRIDDEN_PRICE_LIST })

	@with_cookies({ MULTICOMPANY_COOKIE_NAME: 'Non Existent Company' })
	def test_no_override_if_cookie_is_invalid(self):
		self.assertShoppingCartSettings({ 'price_list': DEFAULT_PRICE_LIST })

	@with_cookies({})  # no cookie
	def test_company_must_be_none_if_no_cookie(self):
		venue_settings = frappe.get_cached_doc("Venue Settings")
		company = venue_settings.multicompany_get_current_company()
		self.assertIsNone(company)

class TestMulticompanyShoppingCartQuotation(BaseTestVenueCartSettings):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()

		cls.item1 = cls.get_multicompany_item(**TEST_ITEM_1)
		cls.item2 = cls.get_multicompany_item(**TEST_ITEM_2)
		cls.item_all_companies = cls.get_multicompany_item(**TEST_ITEM_ALL)

	@classmethod
	def get_multicompany_item(cls, item_code: str, only_companies: list):
		if res := frappe.get_list("Website Item", filters={"item_code": item_code}, limit=1, fields=["name"], ignore_permissions=True):
			frappe.delete_doc("Website Item", res[0].name, ignore_permissions=True)
		it = make_website_item(frappe.get_cached_doc("Item", item_code), save=False)
		it.only_companies = []
		for c in only_companies:
			it.append('only_companies', {'company': c})
		it.save()
		return it

	def make_cart(self, items: list):
		"""
		Adds a list Website Item to cart and return the corresponding quotation.
		The quotation is saved, thus validate() is called.
		"""

		if frappe.session.user != TEST_USER:
			raise ValueError("Invalid test: Use @with_user(TEST_USER) to use the make_cart method.")

		frappe.db.sql("DELETE FROM `tabQuotation` WHERE `contact_email`=%s", TEST_USER)

		try:
			debtor = get_debtors_account(get_shopping_cart_settings())
		except:
			# probably a missing parent account
			venue_settings = frappe.get_cached_doc("Venue Settings")
			company = venue_settings.multicompany_get_current_company()
			debtors_account = frappe.get_doc({
				"doctype": "Account",
				"account_type": "Receivable",
				"root_type": "Asset",
				"is_group": 1,
				"account_name": "_TEST Account Parent for Debtors",
				"parent_account": frappe.get_value("Account", filters={
					"is_group": 1,
					"account_currency": "INR",
					"company": company,
				}, fieldname="name"),
				"account_currency": "INR",
				"company": company,
			}).insert(ignore_permissions=True)
			debtor = get_debtors_account(get_shopping_cart_settings())

		for item in items:
			update_cart(item.item_code, 1)  # save() is called in update_cart(...)
		return _get_cart_quotation()

	def assertQuotationItems(self, quotation, items_code_and_qty: dict):
		items_code_and_qty = {
			(item_code if isinstance(item_code, str) else item_code.item_code): qty
			for item_code, qty in items_code_and_qty.items()
		}
		for q_item in quotation.items:
			if q_item.item_code not in items_code_and_qty:
				print(quotation.as_dict())
				self.fail(f"Unexpected item {q_item.item_code} in quotation.")
			expected_qty = items_code_and_qty[q_item.item_code]
			self.assertAlmostEqual(q_item.qty, expected_qty)
		self.assertEqual(len(quotation.items), len(items_code_and_qty))

	@change_settings('Venue Settings', {'enable_multi_companies': False})  # call this first because of permissions
	@with_cookies({})  # no cookie
	@with_user(TEST_USER)
	def test_cart_nonregression_if_disabled(self):
		quotation = self.make_cart([self.item1, self.item2])
		self.addCleanup(quotation.delete, ignore_permissions=True)  # cleanup
		self.assertEqual(quotation.company, DEFAULT_COMPANY)
		self.assertEqual(quotation.selling_price_list, DEFAULT_PRICE_LIST)
		self.assertQuotationItems(quotation, {self.item1: 1, self.item2: 1})

	@with_cookies({ MULTICOMPANY_COOKIE_NAME: ALT_COMPANY_1 })
	@with_user(TEST_USER)
	def test_cart_exclude_unavailable_items_from_cart1(self):
		# Note: we add self.item_all_companies to the cart to make sure it's not empty.
		quotation = self.make_cart([self.item_all_companies, self.item1, self.item2])
		self.addCleanup(quotation.delete, ignore_permissions=True)  # cleanup

		self.assertEqual(quotation.company, ALT_COMPANY_1)
		self.assertEqual(quotation.selling_price_list, ALT_PRICE_LIST_1)
		self.assertQuotationItems(quotation, {self.item_all_companies: 1, self.item1: 1})

	@with_cookies({ MULTICOMPANY_COOKIE_NAME: ALT_COMPANY_2 })
	@with_user(TEST_USER)
	def test_cart_exclude_unavailable_items_from_cart2(self):
		# Note: we add self.item_all_companies to the cart to make sure it's not empty.
		quotation = self.make_cart([self.item_all_companies, self.item1, self.item2])
		self.addCleanup(quotation.delete, ignore_permissions=True)  # cleanup

		self.assertEqual(quotation.company, ALT_COMPANY_2)
		self.assertEqual(quotation.selling_price_list, ALT_PRICE_LIST_2)
		self.assertQuotationItems(quotation, {self.item_all_companies: 1, self.item2: 1})

	@with_cookies({})  # no cookie
	@with_user(TEST_USER)
	def test_cart_accepts_items_from_default_company_if_no_cookie(self):
		# Here we try to add items to a cart, but none can be added because they can't be sold by the None company.
		# This would ideally raise a MandatoryError for `items`, as no item was added to the cart.
		# But we instead accept those from the default company to avoid changing the
		# behavior of the cart for incorrect use cases of the multi-company feature.
		quotation = self.make_cart([self.item_all_companies, self.item1, self.item2])
		self.addCleanup(quotation.delete, ignore_permissions=True)  # cleanup just in case

		self.assertEqual(quotation.company, DEFAULT_COMPANY)
		self.assertEqual(quotation.selling_price_list, DEFAULT_PRICE_LIST)  # tested elsewhere
		self.assertQuotationItems(quotation, {self.item_all_companies: 1, self.item1: 1, self.item2: 1})

	@change_settings('E Commerce Settings', {'company': ALT_COMPANY_1})
	@with_cookies({ MULTICOMPANY_COOKIE_NAME: ALT_COMPANY_2 })
	@with_user(TEST_USER)
	def test_cart_exclude_unavailable_items_from_cart_even_if_it_means_making_it_empty(self):
		try:
			# Here we try to add items to a cart, but none can be added because they are not available for the company.
			# This should raise a MandatoryError for `items`, as no item was added to the cart.
			quotation = self.make_cart([self.item1])
			self.addCleanup(quotation.delete, ignore_permissions=True)  # cleanup just in case
			print(quotation.as_dict())
			self.fail("Expected a MandatoryError for `items`.")
		except frappe.MandatoryError:
			# 2) A MandatoryError should be raised
			pass  # expected
		except frappe.ValidationError:
			# 3) No other exception should be raised
			raise AssertionError("Expected a MandatoryError for `items`.")

	@with_cookies({ MULTICOMPANY_COOKIE_NAME: ALT_COMPANY_1 })
	@with_user(TEST_USER)
	def test_company_must_be_the_same_as_cookie_if_valid(self):
		venue_settings = frappe.get_cached_doc("Venue Settings")
		company = venue_settings.multicompany_get_current_company()
		if company:
			self.assertEqual(company, ALT_COMPANY_1)
		else:
			self.fail("Failed to retrieve the company from cookies.")

	@change_settings('E Commerce Settings', {'company': ALT_COMPANY_2})
	@with_cookies({ MULTICOMPANY_COOKIE_NAME: ALT_COMPANY_1 })
	@with_user(TEST_USER)
	def test_cart_company_must_be_the_same_as_cookie(self):
		venue_settings = frappe.get_cached_doc("Venue Settings")
		company = venue_settings.multicompany_get_current_company()
		if company:
			self.assertEqual(company, ALT_COMPANY_1)
		else:
			self.fail("Failed to retrieve the company from cookies.")

		quotation = _get_cart_quotation()
		self.addCleanup(quotation.delete, ignore_permissions=True)  # cleanup

		self.assertEqual(quotation.company, company)
