from frappe import _


def get_data():
	return {
		"graph": True,
		"graph_method": "erpnext.accounts.doctype.subscription.subscription.get_chart_data",
		"graph_method_args": {"title": _("Last subscription invoices")},
		"fieldname": "subscription",
		"transactions": [
			{"label": _("Sales"), "items": ["Sales Order", "Sales Invoice"]},
			{"label": _("Payments"), "items": ["Payment Request", "Payment Entry"]},
			{"label": _("Events"), "items": ["Subscription Event"]},
		],
	}
