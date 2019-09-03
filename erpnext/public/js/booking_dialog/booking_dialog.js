import BookingForm from './BookingForm.vue';
frappe.provide("erpnext.booking_dialog");
frappe.provide("erpnext.booking_dialog_update")
frappe.utils.make_event_emitter(erpnext.booking_dialog_update);


erpnext.booking_dialog = class BookingDialog {
	constructor(opts) {
		Object.assign(this, opts);
		this.show()
	}

	show() {
		this.build_dialog()
		frappe.require([
			'/assets/js/frappe-vue.min.js',
			'/assets/js/moment-bundle.min.js',
			'/assets/js/booking-dialog.min.js'
		], () => {
			this.build_calendar()
		});
	}

	read_only() {
		return frappe.session.user === "Guest"
	}

	build_dialog() {
		this.dialog = new frappe.ui.Dialog({
			size: "large",
			fields: [
				{
					fieldname: 'booking_section',
					fieldtype: 'HTML',
				}
			],
			primary_action_label: this.read_only() ? __('Login to select') : __('View in Cart'),
			primary_action: () => {
				this.dialog.hide()
				if (this.read_only()) {
					if(localStorage) {
						localStorage.setItem("last_visited", window.location.pathname);
					}
					window.location.href = "/login"
				} else {
					window.location.href = "/cart"
				}
			}
		})

		if (!this.read_only()) {
			const footer = this.dialog.$wrapper.find(".modal-footer")
			this.secondary_action = footer.prepend(`
				<button type="button" class="btn btn-sm btn-secondary">${__("Reset")}</button>
			`)
			this.secondary_action.on('click', () => {
				frappe.call("erpnext.stock.doctype.item_booking.item_booking.reset_all_booked_slots")
				.then(r => {
					erpnext.booking_dialog_update.trigger('refresh');
				})
			})
		}

		this.dialog.show()
	}

	build_calendar() {
		this.wrapper = this.dialog.fields_dict.booking_section.$wrapper[0];

		new Vue({
			el: this.wrapper,
			render: h => h(BookingForm, {
				props: { item: this.item }
			})
		})
	}
}