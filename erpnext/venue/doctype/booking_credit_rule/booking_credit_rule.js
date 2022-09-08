// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Booking Credit Rule', {
	refresh(frm) {
		frm.trigger("setup_child_tables");
		frm.trigger("get_fields");
		frm.trigger("toggle_applicable_rules");
		frm.trigger("child_table_fields");
	},
	trigger_document(frm) {
		frm.trigger("setup_child_tables")
		frm.trigger("get_fields");
		frm.trigger("common_documents_mapping");
	},
	get_fields(frm) {
		frm.trigger("setup_customer_options")
		frm.trigger("setup_user_options")
		frm.trigger("setup_status_options")
		frm.trigger("setup_time_options")
		frm.trigger("setup_uom_options")
		frm.trigger("setup_item_options")
		frm.trigger("setup_qty_options")
	},
	rule_type(frm) {
		frm.doc.rule_type == "Booking Credits Addition" ? frm.set_value("trigger_action", "On Submit") : frm.set_value("trigger_action", "After Document Start Datetime");
	},
	use_child_table(frm) {
		frm.trigger("child_table_fields");
	},
	child_table(frm) {
		frm.trigger("child_table_fields");
	},
	child_table_fields(frm) {
		if (frm.doc.child_table && frm.doc.trigger_document) {
			frappe.model.with_doctype(frm.doc.trigger_document, () => {
				const meta = frappe.get_meta(frm.doc.trigger_document).fields.map(v => {
					return (v.fieldname == frm.doc.child_table) && v.options ? v : null
				}).filter(f => f != null)
				frm.child_table_name = meta.length && meta[0].options;
				frm.trigger("get_fields");
			})
		} else {
			frm.trigger("get_fields");
		}
	},
	fifo_deduction(frm) {
		frm.trigger("toggle_applicable_rules");
	},
	custom_deduction_rule(frm) {
		frm.trigger("toggle_applicable_rules");
	},
	deduct_real_usage(frm) {
		frm.trigger("toggle_applicable_rules");
	},
	setup_time_options(frm) {
		if (frm.doc.trigger_document) {
			get_fieldtypes_options(frm, frm.doc.trigger_document, ["Datetime"], "start_time_field");
			get_fieldtypes_options(frm, frm.doc.trigger_document, ["Datetime"], "end_time_field");
			get_fieldtypes_options(frm, frm.doc.trigger_document, ["Date"], "date_field");
			get_fieldtypes_options(frm, frm.doc.trigger_document, ["Date"], "recurrence_end");
		}
	},
	setup_date_options(frm) {
		if (frm.doc.trigger_document) {
			frappe.xcall('erpnext.venue.doctype.booking_credit_rule.booking_credit_rule.get_date_options',
				{
					doctype: frm.doc.trigger_document
				}
			)
				.then(r => {
					if (r.length) {
						frm.fields_dict.start_time_field.df.options = [''].concat(r);
						frm.fields_dict.end_time_field.df.options = [''].concat(r);
						frm.fields_dict.date_field.df.options = [''].concat(r);
						frm.refresh_field('start_time_field');
						frm.refresh_field('end_time_field');
						frm.refresh_field('date_field');
					}
				})
		}
	},
	setup_status_options(frm) {
		if (frm.doc.trigger_document) {
			frappe.xcall('erpnext.venue.doctype.booking_credit_rule.booking_credit_rule.get_status_options',
				{
					doctype: frm.doc.trigger_document
				}
			)
				.then(r => {
					frm.fields_dict.expected_status.df.options = r;
					frm.refresh_field('expected_status');
				})
		}
	},
	setup_customer_options(frm) {
		get_link_options(frm, frm.doc.trigger_document, "Customer", "customer_field");
	},
	setup_user_options(frm) {
		get_link_options(frm, frm.doc.trigger_document, "User", "user_field");
	},
	setup_qty_options(frm) {
		get_fieldtypes_options(frm, frm.doc.use_child_table && frm.child_table_name ? frm.child_table_name : frm.doc.trigger_document, ["Int", "Float"], "qty_field");
	},
	setup_uom_options(frm) {
		get_link_options(frm, frm.doc.use_child_table && frm.child_table_name ? frm.child_table_name : frm.doc.trigger_document, "UOM", "uom_field");
	},
	setup_item_options(frm) {
		get_link_options(frm, frm.doc.use_child_table && frm.child_table_name ? frm.child_table_name : frm.doc.trigger_document, "Item", "item_field");
	},
	setup_child_tables(frm) {
		if (frm.doc.trigger_document) {
			frappe.xcall('erpnext.venue.doctype.booking_credit_rule.booking_credit_rule.get_child_tables',
				{
					doctype: frm.doc.trigger_document
				}
			)
				.then(r => {
					// Check match with existing value in case of prefill via Slide Viewer
					const existing_value = frm.doc.child_table;
					frm.fields_dict.child_table.df.options = r;
					if (r.map(v => v.value).includes(existing_value)) {
						frm.set_value('child_table', existing_value)
					}

					frm.refresh_field('child_table');
				})
		}
	},
	toggle_applicable_rules(frm) {
		if (frm.doc.custom_deduction_rule) {
			frm.set_value("deduct_real_usage", 0);
			frm.set_value("fifo_deduction", 0);
		} else if (frm.doc.fifo_deduction) {
			frm.set_value("deduct_real_usage", 0);
		} else {
			frm.set_value("deduct_real_usage", 1);
		}
	},
	common_documents_mapping(frm) {
		if (frm.doc.trigger_document) {
			mapping_fields.forEach(f => {
				const value = document_mapping[frappe.scrub(frm.doc.trigger_document)] ? document_mapping[frappe.scrub(frm.doc.trigger_document)][f] : null;
				value && frm.set_value(f, value);
			})
		}
	}
});

// Use a script instead of configuration to avoid an infinite loop in form rendering
frappe.ui.form.on('Booking Credit Rules', {
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frm.set_df_property(row.parentfield, "reqd", !row.duration_interval, row.parent, "duration")
	},
	duration_interval(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frm.set_df_property(row.parentfield, "reqd", !row.duration_interval, row.parent, "duration")
		frm.set_df_property(row.parentfield, "reqd", row.duration_interval, row.parent, "from_duration")
		frm.set_df_property(row.parentfield, "reqd", row.duration_interval, row.parent, "to_duration")
	}
})

const get_link_options = (frm, doctype, link, field) => {
	if (doctype) {
		frappe.xcall('erpnext.venue.doctype.booking_credit_rule.booking_credit_rule.get_link_options',
			{
				doctype: doctype,
				link: link
			}
		)
			.then(r => {
				if (r.length) {
					frm.fields_dict[field].df.options = [''].concat(r);
					frm.refresh_field(field);
				}
			})
	}
}

const get_fieldtypes_options = (frm, doctype, fieldtypes, field) => {
	if (doctype) {
		frappe.xcall('erpnext.venue.doctype.booking_credit_rule.booking_credit_rule.get_fieldtypes_options',
			{
				doctype: doctype,
				fieldtypes: fieldtypes
			}
		).then(r => {
			if (r.length) {
				frm.fields_dict[field].df.options = [''].concat(r);
				frm.refresh_field(field);
			}
		})
	}
}

const mapping_fields = ["start_time_field", "end_time_field", "customer_field", "user_field", "uom_field", "item_field", "date_field", "qty_field", "child_table"];

const document_mapping = {
	item_booking: {
		"start_time_field": "starts_on",
		"end_time_field": "ends_on",
		"customer_field": "party_name",
		"user_field": "user",
		"item_field": "item"
	},
	sales_order: {
		"child_table": "items",
		"customer_field": "customer",
		"item_field": "item_code",
		"date_field": "transaction_date",
		"uom_field": "uom",
		"qty_field": "qty"
	},
	sales_invoice: {
		"child_table": "items",
		"customer_field": "customer",
		"item_field": "item_code",
		"date_field": "posting_date",
		"uom_field": "uom",
		"qty_field": "qty"
	}
}
