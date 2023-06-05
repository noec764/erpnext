// Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

{% include "frappe/public/js/frappe/utils/web_template.js" %}

frappe.ui.form.on("E Commerce Settings", {
	onload: function(frm) {
		if(frm.doc.__onload && frm.doc.__onload.quotation_series) {
			frm.fields_dict.quotation_series.df.options = frm.doc.__onload.quotation_series;
			frm.refresh_field("quotation_series");
		}

	},
	refresh: function(frm) {
		if (frm.doc.enabled) {
			frm.get_field('store_page_docs').$wrapper.removeClass('hide-control').html(
				`<div>${__("Follow these steps to create a landing page for your store")}:
					<a href="https://docs.erpnext.com/docs/user/manual/en/website/store-landing-page"
						style="color: var(--gray-600)">
						docs/store-landing-page
					</a>
				</div>`
			);
		}

		frappe.model.with_doctype("Website Item", () => {
			const web_item_meta = frappe.get_meta('Website Item');

			const valid_fields = web_item_meta.fields.filter(df =>
				["Link", "Table MultiSelect"].includes(df.fieldtype) && !df.hidden
			).map(df =>
				({ label: df.label, value: df.fieldname })
			);

			frm.get_field("filter_fields").grid.update_docfield_property(
				'fieldname', 'options', valid_fields
			);
		});

		custom_address_form_handler.init(frm);
	},
	enabled: function(frm) {
		if (frm.doc.enabled === 1) {
			frm.set_value('enable_variants', 1);
		}
		else {
			frm.set_value('company', '');
			frm.set_value('price_list', '');
			frm.set_value('default_customer_group', '');
			frm.set_value('quotation_series', '');
		}
	},
});

frappe.ui.form.on("Custom Cart Block", {
	edit_values(frm, cdt, cdn) {
		let row = frm.selected_doc;
		let values = JSON.parse(row.web_template_values || "{}");
		open_web_template_values_editor(row.web_template, values).then((new_values) => {
			frappe.model.set_value(cdt, cdn, "web_template_values", JSON.stringify(new_values));
		});
	},
});

frappe.ui.form.on("Web Form Field", {
	fieldname(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		const fieldname = row.fieldname;
		const df = frappe.get_meta("Address").fields.find(df => df.fieldname === fieldname);
		if (df) {
			const keys = ["label", "fieldtype", "options", "reqd", "description"];
			keys.forEach(key => {
				frappe.model.set_value(cdt, cdn, key, df[key]);
			});
		}
	},

	custom_address_form_add(frm) {
		custom_address_form_handler.addMissingFields(frm);
	},

	reqd(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (!row.reqd && custom_address_form_handler.isRequired(row.fieldname)) {
			frappe.msgprint(__("Mandatory field: {0}", [row.fieldname]));
			frappe.model.set_value(cdt, cdn, "reqd", 1);
		}
	},

	before_custom_address_form_remove(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (custom_address_form_handler.isRequired(row.fieldname)) {
			frappe.throw(__("Mandatory field: {0}", [row.fieldname]));
		}
	},
});

const custom_address_form_handler = {
	init(frm) {
		frappe.model.with_doctype("Address", () => {
			const address_meta = frappe.get_meta("Address");

			const address_fields = address_meta.fields.filter(df =>
				!df.hidden && df.label && !frappe.model.no_value_type.includes(df.fieldtype)
			).map(df => ({ label: df.label, value: df.fieldname }));

			const table = frm.get_field("custom_address_form");
			table.grid.update_docfield_property("fieldname", "options", address_fields);

			if (custom_address_form_handler.getMissingFields(frm).length > 0) {
				this.btn = table.grid.add_custom_button("Add Required Fields", () => {
					custom_address_form_handler.addMissingFields(frm);
				});
				this.btn.removeClass("btn-secondary").addClass("btn-primary");
			}

			this.ready = true;
		});
	},
	isRequired(fieldname) {
		if (!this.ready) return false;
		if (!fieldname) return false;
		return this.getRequiredFields().includes(fieldname);
	},
	getRequiredFields() {
		if (!this.ready) return [];
		return frappe.get_meta("Address").fields.filter(df => df.reqd).map(df => df.fieldname);
	},
	getMissingFields(frm) {
		if (!this.ready) return [];
		const reqd_address_fields = this.getRequiredFields();
		const table = frm.get_field("custom_address_form").grid;
		const existing_fields = table.grid_rows.map(row => row.doc.fieldname);
		const missing_fields = reqd_address_fields.filter(fieldname => !existing_fields.includes(fieldname));
		return missing_fields;
	},
	addMissingFields(frm) {
		if (!this.ready) return;
		const table = frm.get_field("custom_address_form").grid;
		let n = table.grid_rows.length;
		for (const fieldname of this.getMissingFields(frm)) {
			table.add_new_row(++n, null, null, { fieldname });
		}
		this.btn?.hide();
	},
};