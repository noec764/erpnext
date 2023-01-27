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
			method: "erpnext.templates.pages.book.get_items",
			args: {
				filters: this.parent.filter_values
			}
		})
		this.data = items.message
	}

	build_layout() {
		console.log(this.data)
		new erpnext.ProductGrid({
			items: this.data.items,
			products_section: $(this.parent.items_section),
			settings: this.data.settings,
			preference: "Grid View"
		});
	}


}