import ResourceGrid from "./resource_grid";

export default class ItemSection {
	constructor(parent) {
		this.parent = parent;
		this.refresh()
	}

	async refresh() {
		await this.get_data()
		this.build_layout()
	}

	async get_data() {
		const items = await frappe.call({
			method: "erpnext.templates.pages.book_resources.get_items",
			args: {
				filters: this.parent.filter_values
			}
		})
		this.data = items.message
	}

	build_layout() {
		let filtered_items = this.data.items
		if (this.parent.search_type === "client" && this.parent.filter_values.search) {
			const s = this.parent.filter_values.search
			filtered_items = this.data.items.filter(item => {
				return item.item_name.toLowerCase().includes(s.toLowerCase())
			})
		}
		new ResourceGrid({
			items: filtered_items,
			products_section: $(this.parent.items_section),
			settings: this.data.settings,
			filters: this.parent.filter_values
		});

		this.parent.after_refresh?.(this.data)
	}
}