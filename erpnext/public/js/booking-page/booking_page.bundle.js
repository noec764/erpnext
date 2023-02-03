import ItemSection from "./item_section";

class BookingPage {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.item_section = null;
		this.build()
	}

	build() {
		this.wrapper.setAttribute("class", "row")
		this.add_layout()
		this.add_right_sidebar()
		// TODO: Add a search bar
		// this.prepare_toolbar()
		this.add_filters()
		this.reset_search()
	}

	add_layout() {
		this.main_section = document.createElement("div");
		this.main_section.setAttribute("class", "col-sm-8 order-2 order-sm-1")
		this.wrapper.appendChild(this.main_section)

		this.search_section = document.createElement("div");
		this.main_section.appendChild(this.search_section)

		const item_cards_group = document.createElement("div")
		item_cards_group.setAttribute("class", "item-card-group-section")
		this.main_section.appendChild(item_cards_group)

		this.items_section = document.createElement("div");
		this.items_section.setAttribute("class", "row resources-list")
		item_cards_group.appendChild(this.items_section)
	}

	add_right_sidebar() {
		this.right_sidebar = document.createElement("div");
		this.right_sidebar.setAttribute("class", "col-sm-4 order-1 order-sm-2")
		this.wrapper.appendChild(this.right_sidebar)
	}

	prepare_toolbar() {
		$(this.search_section).append(`
			<div class="toolbar d-flex">
			</div>
		`);
		this.prepare_search();

		new erpnext.ProductSearch();
	}

	prepare_search() {
		$(".toolbar").append(`
			<div class="input-group">
				<div class="dropdown w-100" id="dropdownMenuSearch">
					<input type="search" name="query" id="search-box" class="form-control font-md"
						placeholder=${__("Search for Products")}
						aria-label="Product" aria-describedby="button-addon2" autocomplete="off">
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
					<!-- Results dropdown rendered in product_search.js -->
				</div>
			</div>
		`)
	}

	async add_filters() {
		const fields = [
			{
				fieldtype: 'Section Break',
				label: __("Select a start date"),
			},
			{
				fieldtype: 'Datetime',
				fieldname: 'start_date',
				change: () => {
					const doc = this.filters.get_values()
					if (!doc.start_date) {
						return this.set_filter_as_reqd("end_date", false)
					} else if (!doc.end_date) {
						return this.set_filter_as_reqd("end_date", true)
					}
					this.reset_search()
				}
			},
			{
				fieldtype: 'Section Break',
				label: __("Select an end date"),
			},
			{
				fieldtype: 'Datetime',
				fieldname: 'end_date',
				change: () => {
					const doc = this.filters.get_values()
					if (!doc.end_date) {
						return this.set_filter_as_reqd("start_date", false)
					} else if (!doc.start_date) {
						return this.set_filter_as_reqd("start_date", true)
					}
					this.reset_search()
				}
			},
			{
				fieldtype: 'Section Break',
				label: __("Group by resources")
			},
		]

		this.filters = new frappe.ui.FieldGroup({
			fields: fields,
			body: this.right_sidebar
		});

		const item_groups = await frappe.call({
			method: "erpnext.templates.pages.book_resources.get_item_groups",
		})
		item_groups.message.map(group => {
			fields.push({
				fieldtype: 'Check',
				fieldname: frappe.scrub(group),
				label: __(group),
				change: () => {
					this.reset_search()
				}
			})
		})

		this.filters.make();
	}

	set_filter_as_reqd(fieldname, value) {
		$(this.filters.get_field(fieldname).label_area).toggleClass("reqd", value)
	}

	reset_search() {
		const filters = this.filters.get_values()
		this.filter_values = {}

		if (filters.start_date) {
			this.filter_values.start_date = filters.start_date;
		}
		if (filters.end_date) {
			this.filter_values.end_date = filters.end_date;
		}
		const item_groups = Object.keys(filters).filter(f => filters[f] === 1)
		if (item_groups.length) {
			this.filter_values.item_groups = item_groups.map(f => frappe.unscrub(f));
		}

		this.show_items()
	}

	show_items() {
		if (!this.item_section) {
			this.item_section = new ItemSection(this)
		} else {
			this.item_section.refresh()
		}
	}

}

new BookingPage(document.getElementById("booking-page"))