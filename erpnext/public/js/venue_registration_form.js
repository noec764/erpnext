frappe.ready(() => {
	Object.assign(frappe, {
		show_subscription_template_selection: () => {
			frappe.call({
				method: "erpnext.accounts.doctype.subscription.subscription.get_published_subscription_templates"
			}).then(r => {
				if (r.message && r.message.length) {
					const template_cards = r.message.map(template => {
						const template_card = `
							<div class="card-body">
								<h5 class="card-title">${template.name}</h5>
								<div class="card-text">${template.portal_description || ""}</div>
							</div>
							<div class="card-footer">
								<div class="text-right">
									<button class="btn btn-primary" id='${frappe.scrub(template.name)}_subscription' data-subscription='${template.name}'>${__("Select")}</button>
								</div>
							</div>
						`
						let template_image = ''
						if (template.portal_image) {
							template_image = `<img class="card-img-top" src="${template.portal_image}" alt="${template.name}">`
						}

						return `<div class="card" style="width: 18rem;">
							${template_image}
							${template_card}
							</div>`
					}).join("");

					frappe.web_form.get_field("subscription_templates").wrapper.innerHTML = `<div class="subscription-list">${template_cards}</div>`;


					let prevButton = null;
					const webform = document.getElementsByClassName("web-form")[0]
					webform.addEventListener('click', (e) => {
						const isButton = e.target.nodeName === 'BUTTON';

						if (!isButton || !e.target.getAttribute("data-subscription")) {
							return;
						}

						e.target.classList.add('active');
						e.target.innerHTML = __("Selected")

						if(prevButton !== null) {
							prevButton.classList.remove('active');
							prevButton.innerHTML = __("Select")
						}

						prevButton = e.target;
						frappe.web_form.set_value("subscription_template", e.target.getAttribute("data-subscription"))
					})
				}
			})
		}
	})
})