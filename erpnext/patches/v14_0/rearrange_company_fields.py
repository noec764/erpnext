from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	custom_fields = {
		"Company": [
			dict(
				fieldname="hra_section",
				label="HRA Settings",
				fieldtype="Section Break",
				insert_after="asset_received_but_not_billed",
				collapsible=1,
			),
			dict(
				fieldname="basic_component",
				label="Basic Component",
				fieldtype="Link",
				options="Salary Component",
				insert_after="hra_section",
			),
			dict(
				fieldname="hra_component",
				label="HRA Component",
				fieldtype="Link",
				options="Salary Component",
				insert_after="basic_component",
			),
			dict(fieldname="hra_column_break", fieldtype="Column Break", insert_after="hra_component"),
			dict(
				fieldname="arrear_component",
				label="Arrear Component",
				fieldtype="Link",
				options="Salary Component",
				insert_after="hra_column_break",
			),
		]
	}

	create_custom_fields(custom_fields, update=True)
