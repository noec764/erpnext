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
		if (!erpnext.resource_plan.calendar) {
			erpnext.resource_plan.show();
		}
	});
}


class ResourcePlan {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.calendar = null;
	}

	show() {
		frappe.require([
			'moment.bundle.js',
			'resource_calendar.bundle.js',
		], () => {
			this.build_calendar()
		});
	}

	build_calendar() {
		this.calendar = new erpnext.resource_calendar.resourceCalendar(this.wrapper, this.page)
	}
}
