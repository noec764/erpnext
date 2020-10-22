// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Booking Credit Conversion', {
	refresh(frm) {
		if (!frm.is_new() && !frm.conversion_selector) {
			frm.fields_dict.convertible_items.$wrapper.empty();
			const items_area = $('<div>').appendTo(frm.fields_dict.convertible_items.wrapper);
			frm.conversion_selector = new BookingCreditConversionSelector(frm, items_area)
		}
		frm.conversion_selector && frm.conversion_selector.refresh();
	}
});

class BookingCreditConversionSelector{
	constructor(frm, wrapper) {
		this.wrapper = $('<div class="row items-block-list"></div>').appendTo(wrapper);
		this.frm = frm;
		this.make();
	}

	make() {
		this.frm.doc.__onload.all_items.forEach(m => {
			$(`<div class="col-sm-4">
				<div class="checkbox">
					<label><input type="checkbox" class="block-item-check" data-item="${m.item_code}">${m.item_name}</label>
				</div>
			</div>`).appendTo(this.wrapper);
		});
		this.bind();
	}

	refresh() {
		this.wrapper.find(".block-item-check").prop("checked", false);
		this.frm.doc.conversion_table.forEach((d) => {
			this.wrapper.find(".block-item-check[data-item='"+ d.convertible_item +"']").prop("checked", true);
		});
	}

	bind() {
		const me = this;
		this.wrapper.on("change", ".block-item-check", function() {
			var convertible_item = $(this).attr('data-item');
			if($(this).prop("checked")) {
				me.frm.add_child("conversion_table", {"booking_credits_item": me.frm.doc.booking_credits_item, "convertible_item": convertible_item});
			} else {
				// remove from conversion_table
				me.frm.doc.conversion_table = me.frm.doc.conversion_table.map((d) => {
					if (d.convertible_item != convertible_item) {
						return d;
					}
				}).filter(f => f);
			}
			me.frm.dirty();
		});
	}
};