import ItemSection from "./item_section"

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
		this.add_filters()
		this.reset_search()
	}

	add_layout() {
		this.main_section = document.createElement("div");
		this.main_section.setAttribute("class", "col-sm-8")
		this.wrapper.appendChild(this.main_section)

		this.filters_section = document.createElement("div");
		this.main_section.appendChild(this.filters_section)

		const item_cards_group = document.createElement("div")
		item_cards_group.setAttribute("class", "item-card-group-section")
		this.main_section.appendChild(item_cards_group)

		this.items_section = document.createElement("div");
		this.items_section.setAttribute("class", "row products-list")
		item_cards_group.appendChild(this.items_section)
	}

	add_right_sidebar() {
		this.right_sidebar = document.createElement("div");
		this.right_sidebar.setAttribute("class", "col-sm-4")
		this.wrapper.appendChild(this.right_sidebar)
	}

	async add_filters() {
		this.filters = new frappe.ui.FieldGroup({
			fields: [
				{
					fieldtype: 'Datetime',
					fieldname: 'start_date',
					label: __("Start Date"),
					change: () => this.reset_search()
				},
				{
					fieldtype: 'Column Break',
				},
				{
					fieldtype: 'Datetime',
					fieldname: 'end_date',
					label: __("End Date"),
					change: () => this.reset_search()
				},
				{
					fieldtype: 'Column Break',
				},
				{
					fieldtype: 'Select',
					fieldname: 'item_group',
					label: __("Item Group"),
					options: [],
					change: () => this.reset_search()
				},
			],
			body: this.filters_section
		});

		this.filters.make();

		const item_groups = await frappe.call({
			method: "erpnext.templates.pages.book.get_item_groups",
		})
		item_groups.message && this.filters.set_df_property("item_group", "options", ["" , ...item_groups.message])
	}

	reset_search() {
		this.filter_values = this.filters.get_values()
		console.log(this.filter_values)
		this.show_items()
	}

	show_items() {
		if (!this.item_section) {
			this.item_section = new ItemSection(this)
		} else {
			this.item_section.refresh()
		}
		console.log(this.item_section)
	}

}

new BookingPage(document.getElementById("booking-page"))