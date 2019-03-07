# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

DOCTYPE_VERSION = "1.0.0"

def get_data():
	return [
		{
			"version": "1.0.0",
			"fields": ["naming_series", "payment_type", "posting_date", "company", "paid_from", \
				"paid_from_account_currency", "paid_to", "paid_to_account_currency", "paid_amount", \
				"source_exchange_rate", "base_paid_amount", "received_amount", "target_exchange_rate", \
				"base_received_amount", "references", "deductions"],
			"tables": {
				"references": ["reference_doctype", "reference_name"],
				"deductions": ["account", "cost_center", "amount"]
			}
		}
	]
