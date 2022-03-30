from frappe import _


def get_data():
	return {
		"fieldname": "subscription_plan",
		"transactions": [{"label": _("References"), "items": ["Subscription"]}],
	}
