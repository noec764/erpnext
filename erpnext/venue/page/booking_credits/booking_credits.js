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
		this.limit = 20;
		this.date = frappe.datetime.now_date();
		this.make_form();
		this.make_page();
	}

	make_form() {
		this.date_field = this.page.add_field({
			fieldname: 'date',
			label: __('Date'),
			fieldtype:'Date',
			default: frappe.datetime.now_date(),
			change:() => {
				this.date_field = this.date_field.value;
				this.make_page();
			}
		});

		this.customer_field = this.page.add_field({
			fieldname: 'customer',
			label: __('Customer'),
			fieldtype:'Link',
			options:'Customer',
			change:() => {
				this.customer_field = this.customer_field.value;
				this.make_page();
			}
		});

		this.customer_group_field = this.page.add_field({
			fieldname: 'customer_group',
			label: __('Customer Group'),
			fieldtype:'Link',
			options:'Customer Group',
			change:() => {
				this.customer_group = this.customer_group_field.value;
				this.make_page();
			}
		});

		this.form = new frappe.ui.FieldGroup({
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'balance_html'
				}
			],
			body: this.page.body
		});
		this.form.make();
		this.form.wrapper[0].classList.add("frappe-card");
	}

	make_page() {
		frappe.xcall('erpnext.venue.page.booking_credits.booking_credits.get_balance', {
			"customer": this.customer,
			"date": this.date,
			"limit": this.limit,
			"customer_group": this.customer_group
		}).then(r => {
			let result = ""
			if (r.length) {
				result = r.map(customer => {
					return frappe.render_template('booking_credit_dashboard',
						{
							balance: customer.balance,
							customer: customer.customer,
							date: customer.date,
							max_count: customer.max_count
						})
					}).join("");
			} else {
				result = `<span class='text-muted small'>${__("No credits available for any customer")}</span>`;
			}
			this.form.get_field('balance_html').html(result);
		})
	}
}