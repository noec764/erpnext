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
		new ResourceGrid({
			items: this.data.items,
			products_section: $(this.parent.items_section),
			settings: this.data.settings,
			filters: this.parent.filter_values
		});
	}
}