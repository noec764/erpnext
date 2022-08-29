def get_data():
	return {
		"fieldname": "lead",
		"non_standard_fieldnames": {"Quotation": "party_name", "Opportunity": "party_name"},
		"dynamic_links": {
			"party_name": {
				"Quotation": ["Lead", "quotation_to"],
				"Opportunity": ["Lead", "opportunity_from"],
			}
		},
		"transactions": [
			{"items": ["Opportunity", "Quotation", "Prospect"]},
		],
	}
