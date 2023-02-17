frappe.ready(() => {
	Object.assign(frappe, {
		show_subscription_template_selection: () => {
			if (!frappe.web_form.get_field("subscription_templates")) {
				return
			}

			frappe.call({
				method: "erpnext.accounts.doctype.subscription.subscription.get_published_subscription_templates"
			}).then(r => {
				if (r.message && r.message.length) {
					const template_cards = r.message.map(template => {
						const buttonId = `${frappe.scrub(template.name).replace('"', '\\"')}_subscription`
						const template_card = `
							<div class="card-body">
								<h5 class="card-title">${template.name}</h5>
								<div class="card-text">${template.portal_description || ""}</div>
							</div>
							<div class="card-footer">
								<div class="text-right">
									<button class="btn btn-primary" id="${buttonId}">${__("Select")}</button>
								</div>
							</div>
						`
						let template_image = ''
						if (template.portal_image) {
							template_image = `<img class="card-img-top" src="${template.portal_image}" alt="${frappe.utils.escape_html(template.name)}">`
						}

						return `<div class="card subscription-template-card" data-subscription="${frappe.utils.escape_html(template.name)}">
							${template_image}
							${template_card}
							</div>`
					}).join("");

					frappe.web_form.get_field("subscription_templates").wrapper.innerHTML = `<div class="subscription-list">
						${template_cards}
						<style>
							.subscription-template-card {
								width: 18rem;
								cursor: pointer;
							}
							.subscription-template-card.active {
								border-color: var(--primary);
							}
						</style>
					</div>`;

					let prevButton = null;
					const webform = document.getElementsByClassName("web-form")[0];
					webform.addEventListener("click", (e) => {
						const card = e.target.closest(".subscription-template-card");
						if (!card) { return; }

						const templateName = card.getAttribute("data-subscription")
						if (!templateName) { return; }

						const button = card.querySelector("button");
						if (!button) { return; }

						if (prevButton !== null && prevButton !== button) {
							const prevCard = prevButton.closest(".subscription-template-card");
							prevCard.classList.remove("active");
							prevButton.classList.remove("active");
							prevButton.innerText = __("Select");
						}

						card.classList.add("active");
						button.classList.add("active");
						button.innerText = __("Selected");

						prevButton = button;
						frappe.web_form.set_value("subscription_template", templateName);
					})
				}
			})
		}
	})
})