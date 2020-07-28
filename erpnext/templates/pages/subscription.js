frappe.ready(() => {
	frappe.require([
		'/assets/js/moment-bundle.min.js',
		'/assets/js/dialog.min.js',
		'/assets/js/control.min.js',
		'/assets/frappe/js/frappe/utils/datetime.js'
	], () => {
		new subscriptionPortal({})
	});
});

class subscriptionPortal {
	constructor(opts) {
		Object.assign(this, opts)
		this.subscription = null;
		this.subscription_plans = [];
		this.available_subscriptions = [];
		this.$wrapper = document.getElementsByClassName("subscriptions-section")
		this.$current_subscription = document.getElementsByClassName("current-subscription")
		this.$cancellation_section = document.getElementsByClassName("cancellation-options")
		this.$available_subscriptions = document.getElementsByClassName("available-subscriptions")
		this.build()
	}

	build() {
		this.get_data()
		.then(() => {
			this.subscription&&this.build_current_subscription()
			this.subscription&&!this.subscription.cancellation_date&&this.build_plans()
			this.subscription&&!this.subscription.cancellation_date&&this.build_cancellation_section()
			!this.subscription&&this.build_available_subscriptions()
		})
	}

	get_data() {
		return frappe.call("erpnext.templates.pages.subscription.get_subscription_context")
		.then(r => {
			if (r && r.message) {
				Object.assign(this, r.message);
			}
		})
	}

	build_current_subscription() {
		this.$current_subscription[0].innerHTML = `
			<h5 class="subscriptions-section-title">${ __("Your subscription") }</h5>
			<div class="current-subscription-table"></div>
			`
		this.$current_subscription_table = document.getElementsByClassName("current-subscription-table")
		frappe.call("erpnext.templates.pages.subscription.get_subscription_table", {subscription: this.subscription.name})
		.then(r => {
			if (r && r.message) {
				this.$current_subscription_table[0].innerHTML = r.message;
				this.bind_subscription_lines()
			}
		})

		if (this.subscription.cancellation_date) {
			const div = document.createElement('div')
			div.classList.add('subscription-subtitle')
			div.innerHTML = `<h6 class="small muted">${__("This subscription will end on")} ${frappe.datetime.global_date_format(this.subscription.cancellation_date)}</h6>`
			const $title = this.$current_subscription[0].getElementsByClassName("subscriptions-section-title")[0]
			$title.parentNode.insertBefore( div, $title.nextSibling );
		}
	}

	bind_subscription_lines() {
		const me = this;
		this.subscription.plans.map(plan => {
			const el = document.getElementById(`${plan.name}_trash`)
			el && el.addEventListener("click", function(e) {
				return frappe.call("erpnext.templates.pages.subscription.remove_subscription_line", {subscription: me.subscription.name, line: plan.name})
				.then(r => {
					if (r && r.message) {
						this.subscription = r.message;
						frappe.show_alert({message: __("Line removed from your subscription"), indicator: "green"})
						me.build_current_subscription()
					}
				})
			})
		})
	}

	build_plans() {
		const $plans_wrapper = this.$wrapper[0].getElementsByClassName("available-plans")
		if ($plans_wrapper.length) {
			const plans = this.get_plans_html()
			$plans_wrapper[0].innerHTML = `
				<h5 class="subscriptions-section-title">${ __("Your options") }</h5>
				<div class="card-columns">${plans}</div>`
		}
		this.bind_plans()
	}

	get_plans_html() {
		return this.subscription_plans.map(plan => {
			const image = plan.portal_image ? `<img class="card-img-top" src="${plan.portal_image}" alt="${plan.name}">` : ''
			return `<div class="card" style="width: 18rem;">
				${image}
				<div class="card-body">
					<h5 class="card-title">${plan.name}</h5>
					<p class="card-text">${plan.portal_description || ""}</p>
					<button class="btn btn-primary" id=${frappe.scrub(plan.name)}_plan>${__("Add")}</button>
				</div>
			</div>`
		}).join("")
	}

	bind_plans() {
		const me = this;
		this.subscription_plans.map(plan => {
			document.getElementById(`${frappe.scrub(plan.name)}_plan`).addEventListener("click", function(e) {
				return frappe.call("erpnext.templates.pages.subscription.add_plan", {subscription: me.subscription.name, plan: plan.name})
				.then(r => {
					if (r && r.message) {
						this.subscription = r.message;
						frappe.show_alert({message: __("Plan added to your subscription"), indicator: "green"})
						me.build_current_subscription()
					}
				})
			})
		})
	}

	build_available_subscriptions() {
		const subscriptions = this.available_subscriptions.map(sub => {
			const image = sub.portal_image ? `<img class="card-img-top" src="${sub.portal_image}" alt="${sub.name}">` : ''
			return `<div class="card" style="width: 18rem;">
				${image}
				<div class="card-body">
					<h5 class="card-title">${sub.name}</h5>
					<p class="card-text">${sub.portal_description || "" }</p>
					<button class="btn btn-primary" id=${frappe.scrub(sub.name)}_subscription>${__("Subscribe")}</button>
				</div>
			</div>
			`
		}).join("")

		this.$available_subscriptions[0].innerHTML = `<div class="card-columns">${subscriptions}</div>`
		this.bind_available_subscriptions()
	}

	bind_available_subscriptions() {
		this.available_subscriptions.map(sub => {
			document.getElementById(`${frappe.scrub(sub.name)}_subscription`).addEventListener("click", function(e) {
				return frappe.call("erpnext.templates.pages.subscription.new_subscription", {template: sub.name})
				.then(r => {
					if (r && r.message) {
						this.subscription = r.message;
						frappe.show_alert({message: __("Subscription created"), indicator: "green"})
						me.build_current_subscription()
					}
				})
			})
		})
	}

	build_cancellation_section() {
		const me = this;
		this.$cancellation_section[0].innerHTML = 
			`<h5 class="subscriptions-section-title">${ __("Cancellation options") }</h5>
			<button class="btn btn-danger" id="subscription-cancellation-btn">${ __("Cancel my subscription") }</button>
			`
		document.getElementById('subscription-cancellation-btn').addEventListener("click", function(e) {
			new frappe.confirm(__('Cancel this subscription at the end of the current billing period ?'), function() {
				me.cancel_subscription();
			})
		})
	}

	cancel_subscription() {
		return frappe.call("erpnext.templates.pages.subscription.cancel_subscription", {subscription: this.subscription.name})
		.then(r => {
			if (r && r.message) {
				this.subscription = r.message;
				frappe.show_alert({message: __("Subscription created"), indicator: "green"})
				this.build_current_subscription()
			}
		})
	}
}
