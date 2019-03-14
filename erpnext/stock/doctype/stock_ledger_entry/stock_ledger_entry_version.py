# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

DOCTYPE_VERSION = "1.0.0"

def get_data():
	return [
		{
			"version": "1.0.0",
			"fields": ['item_code', 'serial_no', 'batch_no', 'warehouse', 'posting_date',\
				'posting_time', 'voucher_type', 'voucher_no', 'voucher_detail_no', 'actual_qty',\
				'incoming_rate', 'outgoing_rate', 'stock_uom', 'project', 'company', 'fiscal_year'],
			"tables": {},
			"sanitize": True
		}
	]

