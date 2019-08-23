from __future__ import unicode_literals

from frappe import _


def get_data():
	return {
		'fieldname': 'subscription_plan',
		'non_standard_fieldnames': {
			'Subscription': 'plan'
		},
		'transactions': [
			{
				'label': _('References'),
				'items': ['Subscription']
			}
		]
	}
