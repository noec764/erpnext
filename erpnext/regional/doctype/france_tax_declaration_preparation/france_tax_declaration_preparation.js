// Copyright (c) 2022, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('France Tax Declaration Preparation', {
	onload(frm) {
		frm.get_field("deductible_details").$wrapper.empty()
		frm.get_field("collected_details").$wrapper.empty()
	},

	refresh(frm) {
		if (!frm.doc.title) {
			frm.set_value("title", __("VAT Declaration Preparation"))
		}

		frm.trigger("highlight_inconsistencies")
		frm.trigger("get_summary")

		frm.get_field("deductible_vat").$wrapper.on("page_change", () => {
			frm.trigger("highlight_inconsistencies")
		})

		frm.get_field("collected_vat").$wrapper.on("page_change", () => {
			frm.trigger("highlight_inconsistencies")
		})
	},

	get_deductible_vat(frm) {
		frm.events.get_data(frm, "get_deductible_vat", "deductible_details")
	},

	get_collected_vat(frm) {
		frm.events.get_data(frm, "get_collected_vat", "collected_details")
	},

	get_data(frm, method, field) {
		frappe.call({
			method: method,
			doc: frm.doc,
			freeze: true
		}).then((res) => {
			frm.refresh()
			if (res.message) {
				frm.get_field(field).$wrapper.html(res.message)
			}
			frm.trigger("highlight_inconsistencies");
			frm.trigger("get_summary");
			frm.dirty();
		})
	},

	highlight_inconsistencies(frm) {
		frm.doc.deductible_vat.map(d => {
			highlight_inconsistencies(frm, d.doctype, d.name)
		})

		frm.doc.collected_vat.map(d => {
			highlight_inconsistencies(frm, d.doctype, d.name)
		})
	},

	get_summary(frm) {
		frappe.call({
			method: "get_summary",
			doc: frm.doc,
			freeze: true
		}).then((res) => {
			if (res.message) {
				let columns = res.message.columns.map(column => {
					return Object.assign(column, {
						format: (value, row, col, data) => {
							if (data.bold) {
								return value.bold();
							}
							return value || ""
						}
					})
				})

				new DataTable(
					frm.get_field("summary").$wrapper.get(0),
					{
						columns: columns,
						data: res.message.data,
						serialNoColumn: false,
						checkboxColumn: false,
						noDataMessage: __('No Data'),
						disableReorderColumn: true,
						cellHeight: 35,
						language: frappe.boot.lang,
						layout: 'fixed'
					}
				);
			}
		})
	}
});


frappe.ui.form.on('France Tax Declaration Preparation Details', {
	collectible_vat_add(frm, cdt, cdn) {
		highlight_inconsistencies(frm, cdt, cdn);
	},
	deductible_vat_add(frm, cdt, cdn) {
		highlight_inconsistencies(frm, cdt, cdn);
	},
	collectible_vat_remove(frm, cdt, cdn) {
		highlight_inconsistencies(frm, cdt, cdn);
	},
	deductible_vat_remove(frm, cdt, cdn) {
		highlight_inconsistencies(frm, cdt, cdn);
	},
	collectible_vat_move(frm, cdt, cdn) {
		highlight_inconsistencies(frm, cdt, cdn);
	},
	deductible_vat_move(frm, cdt, cdn) {
		highlight_inconsistencies(frm, cdt, cdn);
	},
})


const highlight_inconsistencies = (frm, cdt, cdn) => {
	const row = locals[cdt][cdn]
	if (Math.round(row.tax_rate * row.taxable_amount / 100, 2) != Math.round(row.vat_amount, 2)) {
		frm.get_field(row.parentfield).$wrapper.find(`[data-idx="${row.idx}"]`).css("background-color", "var(--red-50)")
	} else {
		frm.get_field(row.parentfield).$wrapper.find(`[data-idx="${row.idx}"]`).css("background-color", "")
	}
}
