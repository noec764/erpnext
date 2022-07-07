frappe.provide('frappe.slide_viewer_templates')

function get_booking_credit_rule_simplified_slides() {
	return [
		"section:",
		"section:triggers_section",
		// "section:posting_date_section",
		// "section:expiration_section",
		// "section:recurrence_section",
		(index, groupToSlide, globalTitle) => {
			// merge three sections into one
			const slide = groupToSlide([], index) // empty slide
			const posting_date_fields = groupToSlide('section:posting_date_section').fields
			const expiration_fields = groupToSlide('section:expiration_section').fields
			const recurrence_fields = groupToSlide('section:recurrence_section').fields
			slide.fields = [
				...posting_date_fields,
				{ fieldtype: 'Section Break' },
				...expiration_fields,
				{ fieldtype: 'Section Break' },
				...recurrence_fields,
			]
			return slide
		},
		"section:fields_map",
		// "section:applicable_deduction_rules_section",
		// "section:custom_rules_section",
		"*",
	]
}

frappe.slide_viewer_templates['Booking Credits Addition'] = {
	title: __('Booking Credits Addition'),
	with_form: true,
	additional_settings(sv) {
		Object.assign(sv.doc, {
			rule_type: "Booking Credits Addition",
			use_child_table: true,
			applicable_for: "Item",
			trigger_document: "Sales Invoice",
			child_table: "items",
			trigger_action: "On Submit",
			conditions: "doc.subscription",
			expiration_rule: "Add X years",
			expiration_delay: 1
		})
	},
	slideView: {
		title: __("Booking Credits Addition"),
		reference_doctype: "Booking Credit Rule",
		add_fullpage_edit_btn: true,
		slides: get_booking_credit_rule_simplified_slides(),
	},
}

frappe.slide_viewer_templates['Booking Credits Deduction'] = {
	title: __('Booking Credits Deduction'),
	with_form: true,
	additional_settings(sv) {
		Object.assign(sv.doc, {
			rule_type: "Booking Credits Deduction",
		})
	},
	slideView: {
		title: __("Booking Credits Deduction"),
		reference_doctype: "Booking Credit Rule",
		add_fullpage_edit_btn: true,
		slides: get_booking_credit_rule_simplified_slides(),
	},
}
