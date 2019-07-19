from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'graph': True,
		'graph_method': "erpnext.accounts.doctype.subscription.subscription.get_chart_data",
		'graph_method_args': {
			'title': _('Subscription invoices')
		},
		'fieldname': 'subscription',
		'transactions': [
			{
				'label': _('Sales'),
				'items': ['Sales Invoice']
			}
		]
	}