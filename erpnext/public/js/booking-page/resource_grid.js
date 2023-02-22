export default class ResourceGrid {
	/* Options:
		- items: Items
		- settings: E Commerce Settings
		- products_section: Products Wrapper
	*/
	constructor(options) {
		Object.assign(this, options);

		this.products_section.empty();
		this.make();
	}

	make() {
		let me = this;
		let html = ``;

		this.items = this.items.sort((a, b) => {
			return this.is_item_available(b) - this.is_item_available(a);
		});

		this.items.forEach(item => {
			let title = item.web_item_name || item.item_name || item.item_code || "";

			let card_class = "card booking-card";
			if (this.is_item_available(item)) {
				card_class += " booking-available";
			} else {
				card_class += " booking-unavailable";
			}

			html += `<a class="${card_class}" href="${this.get_href(item)}" style="cursor: pointer;">`;
			html += me.get_image_html(item, title);
			html += me.get_card_body_html(item, title, me.settings);
			html += `</a>`;
		});

		let $product_wrapper = this.products_section;
		$product_wrapper.append(html);
	}

	get_href(item) {
		if (!item.route) {
			return '#';
		}
		if (item.__cached_url) {
			return item.__cached_url;
		}

		const { item_groups, ...filters } = this.filters;
		const search_params = new URLSearchParams(filters);
		search_params.append("_back", "booking-search");

		let url = frappe.utils.escape_html(item.route);
		if (!url.startsWith('/')) {
			url = '/' + url;
		}
		url += `?${search_params.toString()}`;

		item.__cached_url = url;
		return url;
	}

	get_image_html(item, title) {
		let image = item.website_image;

		if (image) {
			return `
				<div class="card-img-container">
					<img class="card-img" src="${image}" alt="${frappe.utils.escape_html(title)}">
				</div>
			`;
		} else {
			return `
				<div class="card-img-container">
					<div class="card-img-top no-image">
						${ frappe.get_abbr(title) }
					</div>
				</div>
			`;
		}
	}

	get_card_body_html(item, title, settings) {
		return `
			<div class="card-body text-left card-body-flex" style="width:100%">
				<div style="margin-top: 1rem; display: flex;">
					${this.get_title(item, title)}
				</div>
				<div class="product-category">
					${item.item_group || ''}
				</div>
				${this.get_booking_availability(item)}
				${this.get_primary_button(item, settings)}
			</div>
		`;
	}

	get_title(item, title) {
		const title_html = `
			<div class="ellipsis product-title">
				${ title || '' }
			</div>
		`;
		return title_html;
	}

	is_item_available(item) {
		return item.availabilities && item.availabilities.length;
	}

	get_booking_availability(item) {
		if (this.is_item_available(item)) {
			return `
					<span class="out-of-stock mb-2 mt-1" style="color: var(--primary-color)">
						${ __("Available") }
					</span>
				`;
		} else if (item.availabilities) {
			return `
					<span class="out-of-stock mb-2 mt-1">
						${ __("Unavailable") }
					</span>
				`;
		}

		return ``;
	}

	get_primary_button(item, settings) {
		if (settings.enabled && !item.no_add_to_cart) {
			return `
				<button id="${ item.name }" class="btn btn-sm btn-primary mb-0 mt-0 w-100"
					data-item-code="${ item.item_code }"
					style="padding: 0.25rem 1rem; min-width: 135px;">
					<span class="mr-2">
						<svg class="icon icon-md">
							<use href="#icon-assets"></use>
						</svg>
					</span>
					${ __('Select a slot') }
				</button>
			`;
		} else {
			return ``;
		}
	}
};