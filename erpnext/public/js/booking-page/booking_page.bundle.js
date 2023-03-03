import ItemSection from "./item_section";

class BookingPage {
	constructor(wrapper) {
		this.ready = false
		this.wrapper = wrapper
		this.item_section = null
		this.search_type = "client" // client or server

		this.debounced_show_items = frappe.utils.throttle(this.show_items.bind(this), 250)
		this.build()
	}

	async build() {
		this.add_layout()

		await this.add_filters()
		await this.set_field_values_from_url()

		this.ready = true
		this.refresh_search(true)
	}

	add_layout() {
		this.toolbar = document.createElement("div")
		this.toolbar.setAttribute("class", "toolbar")
		this.wrapper.append(this.toolbar)

		this.items_section = document.createElement("div")
		this.items_section.setAttribute("class", "resources-grid item-card-group-section")
		this.wrapper.appendChild(this.items_section)
	}

	async add_filters() {
		this.add_filter_date()
		this.add_filter_search()
		await this.add_filter_type()
	}

	add_filter_date() {
		const row = document.createElement("label")
		row.setAttribute("class", "filter-date-container")
		row.innerHTML = `<div class="filter-date-label">
			${frappe.utils.icon("calendar", "lg", "text-primary")}
		</div>`
		this.toolbar.appendChild(row)

		const label = row.querySelector(".filter-date-label")
		$(label).tooltip({
			title: __("Date Range"),
			position: "bottom",
		})

		this.date_range = frappe.ui.form.make_control({
			parent: row,
			df: {
				fieldtype: 'DateRange',
				fieldname: 'date_range',
				change: () => this.refresh_search(),
			},
			render_input: true,
		});
	}

	async add_filter_type() {
		const $row = $(`<fieldset class="filter-type"><legend></legend></fieldset>`).appendTo(this.toolbar)

		const make_pill = (label, value, count = -1) => {
			if (count === 0) {
				return
			}
			const $pill = $(`
				<label class="filter-type__pill ellipsis">
					<input type="checkbox" name="" />
					<span></span>
				</label>
			`).appendTo($row)

			const full_label = count >= 0 ? `${label} (${count})` : label
			$pill.find("span").text(full_label)

			const $checkbox = $pill.find("input")
			$checkbox.on("change", () => this.refresh_search())
			$checkbox.attr("name", value)
			return $pill
		}

		this.item_groups = await frappe.call({
			method: "erpnext.templates.pages.book_resources.count_item_groups",
		}).then(r => r.message)

		const options = this.item_groups.sort((a, b) => a.label.localeCompare(b.label))
		for (const option of options) {
			make_pill(option.label, option.value, option.count)
		}

		const $checkboxes = $row.find("input")

		this.filter_by_type = {
			$row,
			get_value() {
				const values = []
				$checkboxes.each((i, checkbox) => {
					if (checkbox.checked) {
						values.push(checkbox.name)
					}
				})
				return values
			},
			set_value(values) {
				$checkboxes.each((i, checkbox) => {
					checkbox.checked = values.includes(checkbox.name)
				})
			},
			set_counts(group_counts = {}) {
				$checkboxes.each((i, checkbox) => {
					const total = group_counts[checkbox.name]?.total || 0
					const new_label = `${__(checkbox.name)} (${total})`
					checkbox.setAttribute("data-total", total)
					checkbox.parentElement.querySelector("span").innerText = new_label
				})
			},
		}
	}

	add_filter_search() {
		const search_label = __("Search")
		const search = $(this.toolbar).append(`
			<div class="search-input">
				<input type="search" class="form-control"
					placeholder="${frappe.utils.escape_html(search_label)}"
					aria-label="${frappe.utils.escape_html(search_label)}"
					autocomplete="off"
				>
				<div class="search-icon">
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor" stroke-width="2" stroke-linecap="round"
						stroke-linejoin="round"
						class="feather feather-search">
						<circle cx="11" cy="11" r="8"></circle>
						<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
					</svg>
				</div>
			</div>
		`).find(".search-input")
		this.search_field = search.get(0).querySelector("input")
		const search_now = frappe.utils.debounce(() => this.refresh_search(), this.search_type === "server" ? 250 : 24)
		this.search_field.addEventListener("keyup", search_now)
		this.search_field.addEventListener("input", search_now)
		this.search_field.addEventListener("change", search_now)
	}

	get_filters() {
		const filter_values = {}

		if (this.date_range.get_value()) {
			const date_range = this.date_range.get_value()
			filter_values.start_date = date_range[0]; // + " 00:00:00"
			filter_values.end_date = date_range[1]; // + " 23:59:59"
		}

		const item_groups = this.filter_by_type && this.filter_by_type.get_value()
		if (item_groups && item_groups.length) {
			filter_values.item_groups = item_groups
		}

		if (this.search_field && this.search_field.value) {
			filter_values.search = this.search_field.value
		}

		return filter_values
	}

	refresh_search(now = false) {
		if (!this.ready) return;

		this.filter_values = this.get_filters();
		this.update_url_with_filter_values();

		if (now) {
			this.show_items()
		} else {
			this.debounced_show_items()
		}
	}

	show_items() {
		if (!this.item_section) {
			this.item_section = new ItemSection(this)
		} else {
			this.item_section.refresh()
		}
	}

	// after_refresh(data) {
	// 	this.filter_by_type.set_counts(data.group_counts)
	// }

	update_url_with_filter_values() {
		const url = new URL(window.location.href)
		const params = new URLSearchParams(url.search)
		const kv = {
			start_date: this.filter_values.start_date,
			end_date: this.filter_values.end_date,
			item_groups: this.filter_values.item_groups?.join(","),
			search: this.filter_values.search,
		}
		for (const [key, value] of Object.entries(kv)) {
			if (value) {
				params.set(key, value)
			} else {
				params.delete(key)
			}
		}
		url.search = params.toString()
		window.history.replaceState({}, "", url.toString())
	}

	async set_field_values_from_url() {
		const params = new URLSearchParams(window.location.search)

		if (params.get("start_date") && params.get("end_date")) {
			await this.date_range.set_value([params.get("start_date"), params.get("end_date")])
		} else {
			const today = frappe.datetime.nowdate()
			const next_week = frappe.datetime.add_days(today, 7)
			await this.date_range.set_value([today, next_week])
		}
		if (params.get("item_groups")) {
			this.filter_by_type.set_value(params.get("item_groups").split(","))
		}
		if (params.get("search")) {
			this.search_field.value = params.get("search")
		}
	}
}

class BookingPageSidebar {
	constructor(wrapper) {
		this.wrapper = wrapper
		this.upcoming_bookings = []
		this.get_upcoming_bookings().then(() => {
			this.build()
		})
	}

	get_upcoming_bookings() {
		return frappe.call({
			method: "erpnext.templates.pages.book_resources.get_upcoming_bookings"
		}).then(r => {
			this.upcoming_bookings = r.message;
		})
	}

	build() {
		const booking_items = Object.keys(this.upcoming_bookings).map(booking => {
			const timetable = this.upcoming_bookings[booking].map(item => {
				return `<div class="small muted">
					· ${frappe.datetime.str_to_user(item.starts_on, false, true)}: ${ frappe.datetime.str_to_user(item.starts_on, true, false) }-${ frappe.datetime.str_to_user(item.ends_on, true, false) }
				</div>`
			}).join('')

			return `<tr class="booking-items">
			<td class="py-2">
				<div class="label">${ booking }</div>
				${timetable}
			</td>
		</tr>`
		}).join('')

		const html = `<div id="upcoming-bookings" class="card frappe-card p-4 sticky-top">
			<h6 class="title">${ __("Upcoming Bookings") }</h6>
			<div class="h-100">
				<div class="card-body p-0">
					<table class="w-100">
						<tbody>
							${booking_items}
						</tbody>
					</table>
					<a class="btn btn-primary btn-sm w-100 mt-4 ellipsis" href="/bookings">
						<span class="ellipsis">${ __("See Bookings") }</span>
					</a>
				</div>
			</div>
		</div>`

		this.wrapper.innerHTML = html;
	}
}

$(document).ready(() => {
	new BookingPage(document.getElementById("booking-page"))
	new BookingPageSidebar(document.getElementById("booking-page-sidebar"))
})
