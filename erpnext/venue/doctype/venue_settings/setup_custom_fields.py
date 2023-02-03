# Copyright (c) 2023, Dokos SAS and contributors
# For license information, please see license.txt


import frappe

## Custom fields for multi company
def get_custom_fields():
	def _get_fields(insert_after: str, depends_on: str = None):
		# hint for translation
		# frappe._('Show only for selected companies')
		# frappe._('Multi-venue mode')

		return [{
			'insert_after': insert_after,
			'fieldname': '_section_break_multicompany',
			'fieldtype': 'Section Break',
			'label': 'Multi-venue mode',
			'collapsible': 0,
			'depends_on': depends_on,
		}, {
			'insert_after': '_section_break_multicompany',
			'fieldname': 'only_companies',
			'fieldtype': 'Table MultiSelect',
			'label': 'Show only for the following companies',
			'options': 'Venue Selected Company',
		}]
	return {
		'Item Group': _get_fields(insert_after='website_specifications', depends_on='show_in_website'),
		'Website Item': _get_fields(insert_after='brand', depends_on='published'),
	}

def multicompany_create_custom_fields(venue_settings):
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	custom_fields = get_custom_fields()
	create_custom_fields(custom_fields)

	# companies = [c.company for c in venue_settings.cart_settings_overrides]
	# for doctype, fields in custom_fields.items():
	# 	for df in fields:
	# 		if df['fieldname'] == 'only_companies':
	# 			docs_to_update = frappe.get_all(doctype)
	# 			for doc in docs_to_update:
	# 				if doctype == "Item Group" and not doc.parent_item_group:
	# 					continue  # ignore root item group
	# 				doc = frappe.get_doc(doctype, doc.name)
	# 				if not doc.only_companies:
	# 					for company in companies:
	# 						doc.append('only_companies', {'company': company})
	# 					doc.save()

def multicompany_delete_custom_fields(venue_settings):
	custom_fields = get_custom_fields()
	for doctype, fields in custom_fields.items():
		for df in fields:
			docname = frappe.db.get_value('Custom Field', {
				'dt': doctype,
				'fieldname': df['fieldname']
			})

			if docname:
				frappe.delete_doc('Custom Field', docname)
