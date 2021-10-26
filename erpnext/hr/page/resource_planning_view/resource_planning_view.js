// Copyright (c) 2021, Dokos SAS and Contributors
// MIT License. See license.txt

frappe.pages['resource-planning-view'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Resource Planning'),
		single_column: true
	});

	erpnext.resource_plan = new ResourcePlan(wrapper);
	$(wrapper).bind('show', function() {
		erpnext.resource_plan.show();
	});
}


class ResourcePlan {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		// $(`<div class="frappe-card"></div>`).appendTo(this.wrapper.find(".page-content"));
		this.page = wrapper.page;
	}

	show() {
		frappe.require([
			'/assets/js/moment-bundle.min.js',
			'assets/js/resource-calendar.min.js',
		], () => {
			this.build_calendar()
		});
	}

	build_calendar() {
		new erpnext.resource_calendar.resourceCalendar(this.wrapper, this.page)
	}
}
