from frappe import _

def get_dashboard_data(data):
	data['transactions'].extend(
		[
			{
				'label': _('Venue'),
				'items': ['Item Booking']
			}
		]
	)

	return data