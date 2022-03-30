from frappe import _


def get_data():
	return {
		"fieldname": "subscription_template",
		"transactions": [{"label": _("Subscriptions"), "items": ["Subscription"]}],
	}
