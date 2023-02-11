export default class ResourceGrid  {
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

		this.items.forEach(item => {
			let title = item.web_item_name || item.item_name || item.item_code || "";
			title =  title.length > 90 ? title.substr(0, 90) + "..." : title;

			html += `<div class="col-xs-12 col-sm-6 col-md-4 item-card"><div class="card">`;
			html += me.get_image_html(item, title);
			html += me.get_card_body_html(item, title, me.settings);
			html += `</div></div>`;
		});

		let $product_wrapper = this.products_section;
		$product_wrapper.append(html);
	}

	get_image_html(item, title) {
		let image = item.website_image;

		if (image) {
			return `
				<div class="card-img-container">
					<a href="/${ item.route || '#' }" style="text-decoration: none;">
						<img class="card-img" src="${ image }" alt="${ title }">
					</a>
				</div>
			`;
		} else {
			return `
				<div class="card-img-container">
					<a href="/${ item.route || '#' }" style="text-decoration: none;">
						<div class="card-img-top no-image">
							${ frappe.get_abbr(title) }
						</div>
					</a>
				</div>
			`;
		}
	}

	get_card_body_html(item, title, settings) {
		let body_html = `
			<div class="card-body text-left card-body-flex" style="width:100%">
				<div style="margin-top: 1rem; display: flex;">
		`;
		body_html += this.get_title(item, title);

		body_html += `</div>`;
		body_html += `<div class="product-category">${ item.item_group || '' }</div>`;

		body_html += this.get_booking_availability(item);
		body_html += this.get_primary_button(item, settings);
		body_html += `</div>`; // close div on line 49

		return body_html;
	}

	get_title(item, title) {
		let title_html = `
			<a href="/${ item.route || '#' }">
				<div class="product-title">
					${ title || '' }
				</div>
			</a>
		`;
		return title_html;
	}

	get_booking_availability(item) {
		if (item.availabilities && item.availabilities.length) {
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
			const { item_groups, ...filters } = this.filters;
			const search_params = new URLSearchParams(filters).toString()
			const url = Object.keys(filters).length ? `${item.route}?${search_params}` : item.route
			return `
				<a href="${url}">
					<div id="${ item.name }" class="btn
						btn-sm btn-primary
						mb-0 mt-0 w-100"
						data-item-code="${ item.item_code }"
						style="padding: 0.25rem 1rem; min-width: 135px;">
						<span class="mr-2">
							<svg class="icon icon-md">
								<use href="#icon-assets"></use>
							</svg>
						</span>
						${ __('Select a slot') }
					</div>
				</a>
			`;
		} else {
			return ``;
		}
	}
};