// Copyright (c) 2021, Dokos SAS and Contributors
// MIT License. See license.txt

import { Calendar } from '@fullcalendar/core';
import resourceTimelinePlugin from '@fullcalendar/resource-timeline';
import interactionPlugin, { Draggable } from '@fullcalendar/interaction';
import adaptivePlugin from '@fullcalendar/adaptive';

frappe.provide("erpnext.resource_calendar")

const group_by_filters = {
	"Department": {
		fieldname: "department",
		label: __("Department"),
		fieldtype: "Link",
		options: "Department"
	},
	"Designation": {
		fieldname: "designation",
		label: __("Designation"),
		fieldtype: "Link",
		options: "Designation"
	},
	"Project": {
		fieldname: "project",
		label: __("Projects"),
		fieldtype: "MultiSelectList",
		get_data: function (txt) {
			return frappe.db.get_link_options('Project', txt);
		}
	},
	"Shift Type": {
		fieldname: "shift_type",
		label: __("Shift Type"),
		fieldtype: "Link",
		options: "Shift Type"
	}
}

erpnext.resource_calendar.resourceCalendar = class ResourceCalendar {
	constructor(wrapper, page) {
		this.wrapper = wrapper;

		this.get_resource_area_columns = this.get_resource_area_columns.bind(this)

		this.page = page;
		$(`<div class="frappe-card resource-calendar mt-4"></div>`).appendTo(this.wrapper.find(".layout-main-section"))

		this.calendar_wrapper = this.wrapper.find(".resource-calendar")[0]

		this.company = frappe.defaults.get_default("company")
		this.projects = []
		this.view = "Employee"
		this.resources_view = "Employee"
		this.group = null
		this.task_enabled = 0
		this.calendar = new Calendar(this.calendar_wrapper, this.get_options());
		this.calendar.render();
		this.add_toolbar();
		this.add_filters_and_dropdowns();
	}

	get_options() {
		const me = this;
		return {
			schedulerLicenseKey: 'GPL-My-Project-Is-Open-Source',
			timeZone: 'UTC',
			locale: frappe.boot.lang || 'en',
			plugins: [resourceTimelinePlugin, interactionPlugin, adaptivePlugin],
			initialView: 'resourceTimelineWeek',
			headerToolbar: {
				left: 'groupByShiftButton',
				center: 'prev,title,next',
				right: 'today,resourceTimelineDay,resourceTimelineWeek,resourceTimelineMonth'
			},
			editable: false,
			selectable: false,
			resourceAreaColumns: this.get_resource_area_columns(),
			resourceGroupField: null,
			slotDuration: { days: 1 },
			weekNumbers: true,
			resourceAreaWidth: "30%",
			droppable: true,
			weekends: true,
			firstDay: 1,
			weekText: __("Week"),
			slotMinWidth: 50,
			contentHeight: "auto",
			expandRows: true,
			refetchResourcesOnNavigate: true,
			buttonText: {
				today: __("Today"),
				month: __("Month"),
				week: __("Week"),
				day: __("Day")
			},
			customButtons: {
				groupByShiftButton: {
					text: me.resources_view == "Shift Type" ? __("Group by employee") : __("Group by shift type"),
						click: function() {
							me.resources_view = me.resources_view == "Shift Type" ? "Employee" : "Shift Type"
							me.set_resource_view_options();
							me.refetch_all();
							me.render_custom_button();
						}
				}
			},
			resources: function (info, callback) {
				return me.get_resource(info, callback)
			},
			events: function (info, callback) {
				return me.get_events(info, callback)
			},
			eventReceive: function (info) {
				let target = info.event.extendedProps.target
				if (target == "AssignTo") {
					const user = info.event.getResources().map((resource) => { return resource.extendedProps.user_id })
					if (user.filter(f => f).length) {
						frappe.xcall('erpnext.hr.page.resource_planning_view.resource_planning_view.add_to_doc', {
							doctype: info.event.extendedProps.reference_type,
							name: info.event.extendedProps.reference_name,
							assign_to: user,
						}).then(r => {
							info.revert()
							me.refetch_all();
						})
					} else {
						frappe.throw(__("Please link this employee to a user to make an assignment."))
					}
					me.refetch_all();
				} else {
					me.show_quick_entry_form(info, target)
				}
			},
			eventClick: function (info) {
				if (info.event.extendedProps.doctype && info.event.extendedProps.docname) {
					me.showPreview(info)
				}
			},
			dateClick: function(info) {
				me.show_quick_entry_form(info, "Shift Assignment")
			},
			eventDidMount: function (info) {
				$(info.el).tooltip({
					title: info.event.title,
					placement: 'top',
					trigger: 'hover',
					container: 'body'
				})
			},
			eventWillUnmount: function (info) {
				$(info.el).tooltip('dispose');
			},
			eventContent: function (args) {
				if (args.event.extendedProps.html_title) {
					return { html: args.event.extendedProps.html_title }
				}
			}
		}
	}

	render_custom_button() {
		const customButtonsOption = this.calendar.getOption('customButtons');
		this.calendar.setOption("customButtons", {
			...customButtonsOption,
			groupByShiftButton: {
				...customButtonsOption.groupByShiftButton,
				text: this.resources_view == "Shift Type" ? __("Group by employee") : __("Group by shift type")
			}
		});
	}

	get_resource_area_columns() {
		const me = this;
		return [
			{
				headerContent: me.resources_view != "Shift Type" ? __('Employee') : "Shift Type",
				field: 'title',
				width: '100%',
				cellContent: function (arg) {
					const green = (arg.resource.extendedProps.working_time || 0) >= (arg.resource.extendedProps.total || 0);
					const html = me.resources_view != "Shift Type" ? `
						<div class="flex align-items-start">
							<div>${frappe.avatar(arg.resource.extendedProps.user_id || arg.fieldValue)}</div>
							<div class="ml-2">
								<div>${arg.fieldValue}</div>
								<div class="small text-muted fc-${green ? 'green' : 'red'}">
									${arg.resource.extendedProps.total || 0} ${__("Hours")} /
									${arg.resource.extendedProps.working_time || 0} ${__("Hours")}
								</div>
							</div>
						</div
					` : `<div>${arg.fieldValue}</div>`
					return { html: html }
				}
			}
		]
	}

	refetch_all() {
		this.calendar.refetchResources();
		this.calendar.refetchEvents();
	}

	get_resource(info, callback) {
		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_resources", {
			company: this.company,
			employee: this.employee,
			department: this.department,
			start: moment(info.start).format("YYYY-MM-DD"),
			end: moment(info.end).format("YYYY-MM-DD"),
			group_by: this.group,
			group_by_value: this.group_by_value,
			resources_view: this.resources_view,
			with_tasks: this.task_enabled
		}).then(r => {
			callback(r)
			this.get_resource_total(info)
		})
	}

	get_events(info, callback) {
		const filters = { company: this.company }
		if (this.employee) {
			filters["employee"] = this.employee
		}

		if (this.projects) {
			filters["projects"] = this.projects
		}

		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_events", {
			start: moment(info.start).format("YYYY-MM-DD"),
			end: moment(info.end).format("YYYY-MM-DD"),
			filters: filters,
			group_by: this.group,
			resources_view: this.resources_view,
			with_tasks: this.task_enabled
		}).then(r => {
			callback(r);
		})
	}

	get_resource_total(info) {
		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_resources_total", {
			start: moment(info.start).format("YYYY-MM-DD"),
			end: moment(info.end).format("YYYY-MM-DD"),
			group_by: this.group,
		}).then(r => {
			Object.keys(r).forEach(key => {
				this.calendar.getResourceById(key) && this.calendar.getResourceById(key).setExtendedProp("total", r[key])
			})
		})
	}

	build_draggable(element, eventData) {
		new Draggable(element, {
			itemSelector: '.btn-draggable',
			eventData: function () {
				return eventData;
			}
		});
	}

	add_toolbar() {
		this.page.clear_inner_toolbar();
		this.add_view_selector();
	}

	bind_draggable_event(dropdown) {
		$(".btn-draggable").off("mousedown").on("mousedown", function () {
			dropdown.dropdown('toggle');
		})
	}

	add_shift_buttons() {
		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_shift_types")
			.then(res => {
				this.shifts_btn = this.page.add_custom_button_group(__("Assign Shift"), null);
				this.shifts_btn.addClass("shift-btn")
				if (!res.length) {
					$(".shift-btn > button").prop('disabled', true);
				} else {
					res.map(r => {
						const eventData = {
							title: r.name,
							duration: r.duration,
							startTime: r.start_time,
							reference_type: "Shift Type",
							reference_name: r.name,
							target: "Shift Assignment"
						}

						const btn = this.page.add_custom_menu_item(
							this.shifts_btn,
							r.name,
							null,
							false,
							null,
							null
						);
						$(btn).addClass("btn-draggable");
						this.build_draggable($(btn)[0], eventData);
						this.bind_draggable_event(this.shifts_btn);
					})
				}
			})
	}

	add_view_selector() {
		const view_selectors = {
			"Employee": "users",
			"Designation": "review",
			"Department": "organization"
		}
		this.views_menu = this.page.add_custom_button_group(__('{0} View', [__(this.view)]), view_selectors[this.view]);
		Object.keys(view_selectors).forEach(v => {
			if (v != this.view) {
				this.page.add_custom_menu_item(
					this.views_menu,
					__('{0} View', [__(v)]),
					() => {
						this.change_view(v)
					},
					true,
					null,
					view_selectors[v]
				);
			}
		})
	}

	set_resource_view_options() {
		this.calendar.setOption("resourceAreaColumns", this.get_resource_area_columns());
		this.calendar.setOption("displayEventTime", this.resources_view != "Shift Type")
	}

	change_view(view) {
		this.view = view;
		this.group = view != "Employee" ? view : null;
		this.task_enabled = this.view == "Project" ? 1: 0;

		this.calendar.setOption("resourceGroupField", this.group ? this.group.toLowerCase() : null);

		this.page.standard_actions.empty();
		this.add_view_selector();
		this.add_filters_and_dropdowns()
		this.refetch_all();
	}

	showPreview(info) {
		this.preview = new EventPreview(info, this)
	}

	add_filters_and_dropdowns() {
		this.page.clear_fields();
		this.group_by_filter = null;
		this.add_company_filter();
		this.add_employee_filter();
		this.add_group_by_filter();
		if (this.view == "Employee") {
			this.add_department_filter();
		}
		this.add_shift_buttons();
	}

	add_company_filter() {
		this.company_filter = this.page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_default("company"),
			reqd: 1,
			change: () => {
				this.company = this.company_filter.get_value() || frappe.defaults.get_default("company")
				this.refetch_all()
			}
		})
	}

	add_employee_filter() {
		this.employee_filter = this.page.add_field({
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			change: () => {
				this.employee = this.employee_filter.get_value();
				this.refetch_all()
			}
		})
	}

	add_department_filter() {
		const options = {
			...group_by_filters["Department"],
			change: () => {
				this.department = this.department_filter.get_value();
				this.refetch_all()
			}
		}
		this.department_filter = this.page.add_field(options)
	}

	add_group_by_filter() {
		if (this.group && !this.group_by_filter) {
			const options = {
				...group_by_filters[this.group],
				change: () => {
					this.group_by_value = this.group_by_filter.get_value();
					this.refetch_all()
				}
			}
			this.group_by_filter = this.page.add_field(options)
		}
	}

	show_quick_entry_form(info, target) {
		frappe.model.with_doctype(target, () => {
			let new_doc = frappe.model.get_new_doc(target);
			new_doc.employee = info.event ? info.event.getResources().map((resource) => { return resource.extendedProps.employee_id })[0]:
				info.resource && info.resource.extendedProps.employee_id
			new_doc.company = this.company
			new_doc.department = info.resource && info.resource.extendedProps.department
			new_doc.designation = info.resource && info.resource.extendedProps.designation
			new_doc.shift_type = info.event&&info.event.extendedProps.reference_name
			new_doc.start_date = moment(info.event ? info.event.start : info.date).format("YYYY-MM-DD")
			new_doc.end_date = moment(info.event ? info.event.end : info.date).format("YYYY-MM-DD")

			frappe.ui.form.make_quick_entry(target, (doc) => {
				frappe.set_route(frappe.get_route_str())
				info.revert&&info.revert();
				this.refetch_all();
			}, null, new_doc, true);

			frappe.quick_entry.dialog.get_close_btn().on('click', () => {
				info.revert&&info.revert();
				frappe.quick_entry.dialog.hide();
			});
		});
	}
}


class EventPreview {
	constructor(info, resource_calendar) {
		this.info = info
		this.calendar = resource_calendar
		this.element = $(info.el)
		this.setup_dialog();
	}

	setup_dialog() {
		this.identify_doc();
		this.get_preview_data().then(preview_data => {
			preview_data && this.init_preview(preview_data)
		})
	}

	init_preview(preview_data) {
		this.dialog = new frappe.ui.Dialog({
			fields: [
				{
					fieldname: 'content',
					fieldtype: 'HTML'
				}
			]
		})

		if (this.info.event.extendedProps.primary_action) {
			this.dialog.set_primary_action(this.info.event.extendedProps.primary_action_label, () => {
				frappe.xcall(this.info.event.extendedProps.primary_action, {
					doctype: this.doctype,
					name: this.name
				}).then(() => {
					this.calendar.refetch_all()
					this.dialog.hide()
				})
			});
		}

		if (this.info.event.extendedProps.secondary_action) {
			this.dialog.set_secondary_action(() => {
				frappe.xcall(this.info.event.extendedProps.secondary_action, {
					doctype: this.doctype,
					name: this.name
				}).then(() => {
					this.calendar.refetch_all()
					this.dialog.hide()
				})
			});
			this.dialog.set_secondary_action_label(this.info.event.extendedProps.secondary_action_label);
		}

		let $wrapper = this.dialog.get_field("content").$wrapper
		$(`
			<div class="resource-event-preview">
				<div class="resource-event-body resource-event-content">
					${this.get_dialog_html(preview_data)}
				</div>
			</div>
		`).appendTo($wrapper);

		this.dialog.show()
	}

	identify_doc() {
		this.doctype = this.info.event.extendedProps.doctype;
		this.name = this.info.event.extendedProps.docname;
		this.href = frappe.utils.get_form_link(this.doctype, this.name);
	}

	get_preview_data() {
		return frappe.xcall('frappe.desk.link_preview.get_preview_data', {
			'doctype': this.doctype,
			'docname': this.name,
			'force': true
		});
	}

	get_dialog_html(preview_data) {
		if (!this.href) {
			this.href = window.location.href;
		}

		if (this.href && this.href.includes(' ')) {
			this.href = this.href.replace(new RegExp(' ', 'g'), '%20');
		}

		let dialog_content = `
			<div class="preview-header">
				<div class="preview-header">
					${this.get_image_html(preview_data)}
					<div class="preview-name">
						<a href=${this.href}>${__(preview_data.preview_title)}</a>
					</div>
					<div class="text-muted preview-title">${this.get_id_html(preview_data)}</div>
				</div>
			</div>
			<hr>
			<div class="resource-event-body">
				${this.get_content_html(preview_data)}
			</div>
		`;

		return dialog_content;
	}

	get_id_html(preview_data) {
		let id_html = '';
		if (preview_data.preview_title !== preview_data.name) {
			id_html = `<a class="text-muted" href=${this.href}>${preview_data.name}</a>`;
		}

		return id_html;
	}

	get_image_html(preview_data) {
		let avatar_html = frappe.get_avatar(
			"avatar-medium",
			preview_data.preview_title,
			preview_data.preview_image
		);

		return `<div class="preview-image">
			${avatar_html}
		</div>`;
	}

	get_content_html(preview_data) {
		let content_html = '';

		Object.keys(preview_data).forEach(key => {
			if (!['preview_image', 'preview_title', 'name'].includes(key)) {
				let value = frappe.ellipsis(preview_data[key], 280);
				let label = key;
				content_html += `
					<div class="preview-field">
						<div class="preview-label text-muted">${__(label)}</div>
						<div class="preview-value">${value}</div>
					</div>
				`;
			}
		});

		return `<div class="preview-table">${content_html}</div>`;
	}
}
