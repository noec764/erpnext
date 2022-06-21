// Copyright (c) 2020, Dokos SAS and Contributors
// See license.txt

import { Calendar } from '@fullcalendar/core';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import interactionPlugin from '@fullcalendar/interaction';
import dayGridPlugin from '@fullcalendar/daygrid';
import EventEmitterMixin from 'frappe/public/js/frappe/event_emitter';

frappe.provide("erpnext.booking_section");
frappe.provide("erpnext.booking_section_update")

erpnext.booking_section_update = {}

erpnext.booking_section = class BookingDialog {
	constructor(opts) {
		Object.assign(this, opts);
		Object.assign(erpnext.booking_section_update, EventEmitterMixin);

		this.read_only = frappe.session.user === "Guest";
		this.wrapper = document.getElementsByClassName(this.parentId)[0];

		frappe.get_user_lang().then(() => {
			this.build_calendar();
		});
	}

	build_calendar() {
		this.calendar = new BookingCalendar(this)

		erpnext.booking_section_update.on("update_calendar", r => {
			this.uom = r;
			this.calendar.booking_selector&&this.calendar.booking_selector.empty();
			this.calendar.fullCalendar&&this.calendar.fullCalendar.refetchEvents();
		})
	}

	destroy_calendar() {
		this.calendar.destroy();
	}
}

class BookingCalendar {
	constructor(parent) {
		this.parent = parent;
		this.slots = [];
		this.booking_selector = null;
		this.locale = frappe.get_cookie('preferred_language') || frappe.boot.lang || 'en';

		this.render();
	}

	render() {
		const calendarEl = $('<div></div>').appendTo($(this.parent.wrapper));
		this.fullCalendar = new Calendar(
			calendarEl[0],
			this.calendar_options()
		)
		this.fullCalendar.render();
	}

	get_header_toolbar() {
		return {
			left: '',
			center: 'prev,title,next',
			right: 'today',
		}
	}

	set_option(option, value) {
		this.fullCalendar&&this.fullCalendar.setOption(option, value);
	}

	get_option(option) {
		return this.fullCalendar&&this.fullCalendar.getOption(option);
	}

	destroy() {
		this.fullCalendar&&this.fullCalendar.destroy();
		document.getElementById('alternative-item').remove();
	}

	getSelectAllow(selectInfo) {
		return moment().diff(selectInfo.start) <= 0
	}

	getValidRange() {
		return { start: moment().add(1,'d').format("YYYY-MM-DD") }
	}

	set_loading_state(state) {
		state ? frappe.freeze(__("Please wait...")) : frappe.unfreeze();
	}

	calendar_options() {
		const me = this;
		return {
			eventClassNames: 'booking-calendar',
			initialView: "dayGridMonth",
			contentHeight: 'auto',
			headerToolbar: me.get_header_toolbar(),
			weekends: true,
			buttonText: {
				today: __("Today"),
				timeGridWeek: __("Week"),
				listDay: __("Day")
			},
			plugins: [
				timeGridPlugin,
				listPlugin,
				interactionPlugin,
				dayGridPlugin
			],
			showNonCurrentDates: false,
			locale: this.locale,
			timeZone: frappe.boot.timeZone || 'UTC',
			initialDate: this.parent.date ? moment(this.parent.date).format("YYYY-MM-DD") : moment().add(1,'d').format("YYYY-MM-DD"),
			noEventsContent: __("No slot available"),
			selectAllow: this.getSelectAllow,
			validRange: this.getValidRange,
			defaultDate: this.getDefaultDate,
			displayEventTime: false,
			dateClick: function(info) {
				me.booking_selector = new BookingSelector({
					parent: me,
					date_info: info
				})
			},
			datesSet: (info) => {
				this.booking_selector&&this.booking_selector.empty();
			},
			events: function(info, callback) {
				frappe.call("erpnext.venue.doctype.item_booking.item_booking.get_availabilities", {
					start: moment(info.start).format("YYYY-MM-DD"),
					end: moment(info.end).format("YYYY-MM-DD"),
					item: me.parent.item,
					uom: me.parent.uom
				}).then(result => {
					result.message.map(r => {
						r.display = 'background'
						r.textColor = "#117f35"
						r.allDay = 1
					})
					me.slots = result.message;
					callback(result.message);

					if (me.parent.date && !me.booking_selector) {
						me.booking_selector = new BookingSelector({
							parent: me,
							date_info: {date: me.parent.date}
						})
					} else {
						me.booking_selector && me.booking_selector.make()
					}
				})
			},
		}
	}
}

class BookingSelector {
	constructor(opts) {
		Object.assign(this, opts);

		this.make()
	}

	make() {
		this.slots = this.parent.slots.filter(s => (
			frappe.datetime.get_date(s.start) <= frappe.datetime.get_date(this.date_info.date)
			) && (
				frappe.datetime.get_date(this.date_info.date) <= frappe.datetime.get_date(s.end)
			)
		)

		this.build();
		this.render();
	}

	build() {
		const me = this;
		const slots_div = this.slots.length ? this.slots.sort((a,b) => new Date(a.start) - new Date(b.start)).map(s => {
			return `<div class="timeslot-options mb-4 px-4" data-slot-id="${s.id}">
				<button class="btn btn-outline-secondary ${s.status == 'selected' ? 'selected' : ''}" type="button">
					<div>
						${moment(s.start).locale(this.parent.locale).format('LT')} - ${moment(s.end).locale(this.parent.locale).format('LT')}
					</div>
				</button>
			</div>`
		}): [];

		this.$content = $(`<div>
			<h2 class="timeslot-options-title mb-4">${this.date_info.date ? moment(this.date_info.date).locale(this.parent.locale).format('LL') : ""}</h2>
			${slots_div.join('')}
		</div>`)

		this.$content.find('.timeslot-options').on('click', function() {
			const selected_slot = me.slots.filter(f => f.id == $(this).attr("data-slot-id"));
			me.select_slot(selected_slot)
		})

	}

	empty() {
		$(".booking-selector").empty()
	}

	render() {
		this.empty()
		$(".booking-selector").append(this.$content)
	}

	select_slot(selected_slot) {
		if (selected_slot.length) {
			selected_slot = selected_slot[0]

			if (frappe.session.user == "Guest") {
				return window.location = `/login?redirect-to=${window.location.pathname}?date=${selected_slot.start}`
			}

			if (selected_slot.status == "selected") {
				this.remove_booked_slot(selected_slot.id)
			} else {
				this.book_new_slot(selected_slot)
			}
		}
	}

	book_new_slot(event) {
		frappe.call("erpnext.venue.doctype.item_booking.item_booking.book_new_slot", {
			start: moment.utc(event.start).format("YYYY-MM-DD H:mm:SS"),
			end: moment.utc(event.end).format("YYYY-MM-DD H:mm:SS"),
			item: this.parent.parent.item,
			uom: this.parent.parent.uom,
			user: frappe.session.user
		}).then(r => {
			this.update_cart(r.message.name, 1)
		})
	}

	remove_booked_slot(booking_id) {
		this.update_cart(booking_id, 0)
	}

	update_cart(booking, qty) {
		erpnext.e_commerce.shopping_cart.shopping_cart_update({
			item_code: this.parent.parent.item,
			qty: qty,
			uom: this.parent.parent.uom,
			booking: booking,
			cart_dropdown: true
		}).then(() => {
			this.parent.fullCalendar&&this.parent.fullCalendar.refetchEvents();
		})
	}
}
