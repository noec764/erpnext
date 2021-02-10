frappe.pages['booking-credits'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Booking Credits Balance'),
		single_column: true
	});

	new erpnext.bookingCreditsBalance(page);
}

erpnext.bookingCreditsBalance = class BookingCreditsBalance {
	constructor(page) {
		this.page = page;
		this.customer = null;
		this.customer_group = null;
		this.balances = [];
		this.limit = 20;
		this.limit_start = 0;
		this.sort_by = 'customer';
		this.sort_order = 'asc';
		this.loading = false;
		this.date = frappe.datetime.now_date();
		this.make_form();
		this.make_sort_selector();
		this.get_data();
	}

	make_form() {
		this.date_field = this.page.add_field({
			fieldname: 'date',
			label: __('Date'),
			fieldtype:'Date',
			default: frappe.datetime.now_date(),
			change:() => {
				this.date = this.date_field.value;
				this.balances = [];
				this.limit_start = 0;
				this.get_data();
			}
		});

		this.customer_field = this.page.add_field({
			fieldname: 'customer',
			label: __('Customer'),
			fieldtype:'Link',
			options:'Customer',
			change:() => {
				this.customer = this.customer_field.value;
				this.balances = [];
				this.limit_start = 0;
				this.get_data();
			}
		});

		this.customer_group_field = this.page.add_field({
			fieldname: 'customer_group',
			label: __('Customer Group'),
			fieldtype:'Link',
			options:'Customer Group',
			change:() => {
				this.customer_group = this.customer_group_field.value;
				this.balances = [];
				this.limit_start = 0;
				this.get_data();
			}
		});

		this.form = new frappe.ui.FieldGroup({
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'balance_html'
				},
				{
					fieldtype: 'HTML',
					fieldname: 'more_html',
					hidden: 1
				}
			],
			body: this.page.body
		});
		this.form.make();
		this.form.wrapper[0].classList.add("frappe-card");
	}

	make_sort_selector() {
		const me = this;
		new frappe.ui.SortSelector({
			parent: this.page.wrapper.find('.page-form'),
			args: {
				sort_by: 'customer',
				sort_order: 'asc',
				options: [
					{fieldname: 'customer', label: __('Customer Name')},
					{fieldname: 'max_count', label: __('Balance')}
				]
			},
			change: function(sort_by, sort_order) {
				me.balances = [];
				me.limit_start = 0;
				me.sort_by = sort_by ? sort_by: me.sort_by;
				me.sort_order = sort_order ? sort_order : me.sort_order;
				!me.balances.length ? me.get_data() : me.render_balances()
			}
		});
	}

	get_data() {
		if (!this.loading) {
			this.loading = true;
			frappe.xcall('erpnext.venue.page.booking_credits.booking_credits.get_balance', {
				"customer": this.customer,
				"date": this.date,
				"limit": this.limit,
				"limit_start": this.limit_start,
				"customer_group": this.customer_group,
				"sort_order": this.sort_order
			}).then(r => {
				if (r.length) {
					r.length == 20 ? this.show_more_btn() : this.hide_more_btn();
					r.forEach(value => {
						!this.balances.some(d => { d.customer == value.customer})&&this.balances.push(value);
					})
					this.limit_start += this.limit;

					this.render_balances();

				} else if (!this.balances.length) {
					this.form.get_field('balance_html').$wrapper.html(`<span class='text-muted small'>${__("No credits available for any customer")}</span>`);
				} else {
					this.hide_more_btn();
				}

				this.loading = false;
			})
		}
	}

	prepare_data() {
		this.balances.sort((a, b) => {
			return a[this.sort_by] - b[this.sort_by];
		});

		(this.sort_order == "desc") && this.balances.reverse();
	}

	render_balances() {
		this.prepare_data()

		const result = this.balances.map(customer => {

			return frappe.render_template('booking_credit_dashboard',
				{
					balance: Object.keys(customer.balance).map(f => { return {...customer.balance[f][0], item: f}}),
					customer: customer.customer,
					date: this.date,
					max_count: customer.max_count
				})
			}).join("");
		this.form.get_field('balance_html').$wrapper.html(result);
		this.bind_reconciliation_btns();
	}

	show_more_btn() {
		this.form.get_field('more_html').$wrapper.toggleClass("hide-control", false)
		this.form.get_field('more_html').html(`<button class="btn btn-default">${__("More")}</button>`);

		this.form.get_field('more_html').$wrapper.on("click", (e) => {
			this.get_data()
		})
	}

	hide_more_btn() {
		this.form.get_field('more_html').$wrapper.toggleClass("hide-control", true)
	}

	bind_reconciliation_btns() {
		this.form.get_field('balance_html').$wrapper.find('.uom-reconciliation-btn').on("click", e => {
			frappe.xcall("erpnext.venue.page.booking_credits.booking_credits.reconcile_credits", {
				customer: $(e.target).attr("data-customer"),
				target_uom: $(e.target).attr("data-uom"),
				target_item: $(e.target).attr("data-target-item"),
				source_item: $(e.target).attr("data-source-item"),
				date: this.date
			}).then(r => {
				frappe.show_alert(r)

				this.balances = [];
				this.limit_start = 0;
				this.get_data();
			})
		})
	}
}