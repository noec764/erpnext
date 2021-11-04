// Copyright (c) 2021, Dokos SAS and Contributors
// MIT License. See license.txt

import { Calendar } from '@fullcalendar/core';
import resourceTimelinePlugin from '@fullcalendar/resource-timeline';
import interactionPlugin, { Draggable } from '@fullcalendar/interaction';
import _default from '@fullcalendar/premium-common';

frappe.provide("erpnext.resource_calendar")

erpnext.resource_calendar.resourceCalendar = class ResourceCalendar {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		$(`<div class="frappe-card resource-calendar mt-4"></div>`).appendTo(this.wrapper.find(".layout-main-section"))

		this.calendar_wrapper = this.wrapper.find(".resource-calendar")[0]

		this.company = frappe.defaults.get_default("company")
		this.projects = []
		this.view = "Employee"
		this.calendar = new Calendar(this.calendar_wrapper, this.get_options());
		this.calendar.render();
		this.add_toolbar();
		this.add_filters();
	}

	get_options() {
		const me = this;
		return {
			schedulerLicenseKey: 'GPL-My-Project-Is-Open-Source',
			timeZone: 'UTC',
			locale: frappe.boot.lang || 'en',
			plugins: [ resourceTimelinePlugin, interactionPlugin ],
			initialView: 'resourceTimelineWeek',
			headerToolbar: {
				left: 'title',
				center: 'prev,today,next',
				right: 'resourceTimelineDay,resourceTimelineWeek,resourceTimelineMonth'
			},
			editable: false,
			resourceAreaHeaderContent: null,
			resourceAreaColumns: this.get_resource_area_columns(),
			slotDuration: { days: 1 },
			weekNumbers: true,
			resourceAreaWidth: "30%",
			droppable: true,
			weekends: false,
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
			resources: function(info, callback) {
				return me.get_resource(info, callback)
			},
			events: function(info, callback) {
				return me.get_events(info, callback)
			},
			eventReceive: function(info) {
				let target = info.event.extendedProps.target
				if (target == "AssignTo") {
					frappe.xcall('erpnext.hr.page.resource_planning_view.resource_planning_view.add_to_doc', {
						doctype: info.event.extendedProps.reference_type,
						name: info.event.extendedProps.reference_name,
						assign_to: info.event.getResources().map((resource) => { return resource.id }),
					}).then(r => {
						if (!r) {
							info.revert()
						}
					})
					me.refetch_all();
				} else {
					me.show_quick_entry_form(info, target)
				}
			},
			eventClick: function(info) {
				if(info.event.extendedProps.doctype && info.event.id) {
					me.showPreview(info)
				}
			},
			eventDidMount: function(info) {
				$(info.el).tooltip({
					title: info.event.title,
					placement: 'top',
					trigger: 'hover',
					container: 'body'
				})
			},
			eventWillUnmount: function(info) {
				$(info.el).tooltip('dispose');
			},
			eventContent: function(args) {
				if (args.event.extendedProps.html_title) {
					return { html: args.event.extendedProps.html_title }
				}
			}
		}
	}

	get_resource_area_columns() {
		let columns = [
			{
				headerContent: __('Employee'),
				field: 'title',
				width: this.view == "Employee" ? '80%' : '50%',
				cellContent: function(arg) {
					const html = `
						<div class="flex align-items-start">
							<div>${frappe.avatar(arg.resource.extendedProps.user_id || arg.fieldValue)}</div>
							<div class="ml-2">
								<div>${arg.fieldValue}</div>
								<div class="small text-muted">${arg.resource.extendedProps.working_time || 0} ${__("Hours")}</div>
							</div>
						</div>
					`
					return { html: html }
				}
			},
			{
				headerContent: __('Total'),
				field: 'total',
				width: '20%',
				cellContent: function(info) {
					const green = (info.resource.extendedProps.working_time || 0) >= (info.fieldValue || 0);
					return { html: `<div class="fc-${green ? 'green' : 'red'} font-weight-bold">${info.fieldValue || 0} ${__("H")}</div>`}
				},
				cellClassNames: "small"
			}
		]

		if (this.view == "Department") {
			columns.unshift(
				{
					group: true,
					headerContent: __('Department'),
					field: 'department',
					width: '30%'
				}
			)
		}

		return columns
	}

	refetch_all() {
		this.calendar.refetchEvents();
		this.calendar.refetchResources();
	}

	get_resource(info, callback) {
		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_resources", {
			company: this.company,
			department: this.department,
			employee: this.employee,
			start: moment(info.start).format("YYYY-MM-DD"),
			end: moment(info.end).format("YYYY-MM-DD"),
			group_by: this.view.toLowerCase()
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

		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_events", {
			start: moment(info.start).format("YYYY-MM-DD"),
			end: moment(info.end).format("YYYY-MM-DD"),
			filters: filters
		}).then(r => {
			callback(r);
		})
	}

	get_resource_total(info) {
		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_resources_total", {
			start: moment(info.start).format("YYYY-MM-DD"),
			end: moment(info.end).format("YYYY-MM-DD")
		}).then(r => {
			Object.keys(r).forEach(key => {
				this.calendar.getResourceById(key) && this.calendar.getResourceById(key).setProp("total", r[key])
			})
		})
	}

	build_draggable(element, eventData) {
		new Draggable(element, {
			itemSelector: '.btn-draggable',
			eventData: function() {
				return eventData;
			}
		});
	}

	add_toolbar() {
		this.page.clear_inner_toolbar();
		this.add_shift_buttons();
		this.add_view_selector();
	}

	bind_draggable_event(dropdown) {
		$(".btn-draggable").off("mousedown").on("mousedown", function(){
			dropdown.dropdown('toggle');
		})
	}

	add_shift_buttons() {
		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_shift_types")
		.then(res => {
			this.shifts_btn = this.add_button_group(__("Assign Shift"), null, "ml-auto shift-btn")
			if (!res.length) {
				$(this.shifts_btn).disable()
			} else {
				res.map(r => {
					const eventData = {
						title: r.name,
						duration: r.duration,
						startTime: r.startTime,
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

	add_tasks_buttons() {
		frappe.xcall("erpnext.hr.page.resource_planning_view.resource_planning_view.get_tasks", {projects: this.projects})
		.then(res => {
			this.tasks_btn = this.add_button_group(__("Assign Task"), null, "ml-auto task-btn")
			if (!res.length) {
				$(this.tasks_btn).disable()
			} else {
				res.map(r => {
					const eventData = {
						title: r.name,
						duration: r.duration,
						startTime: r.startTime,
						reference_type: "Task",
						reference_name: r.name,
						target: "AssignTo"
					}

					const btn = this.page.add_custom_menu_item(
						this.tasks_btn,
						`
							<div>${r.subject}</div>
							<div class="small">${r.project}</div>
							<div class="small text-muted">${r.name}</div>
						`,
						null,
						false,
						null,
						null
					);
					$(btn).addClass("btn-draggable");
					this.build_draggable($(btn)[0], eventData);
					this.bind_draggable_event(this.tasks_btn);
				})
			}
		})
	}

	remove_tasks_buttons() {
		$(".task-btn").remove()
	}

	toggle_shifts_button() {
		if (!this.shifts_btn) {
			this.add_shift_buttons()
		}
		this.view!="Project" ? $(".shift-btn").show() : $(".shift-btn").hide();
	}

	toggle_tasks_button() {
		if (!this.tasks_btn) {
			this.add_tasks_buttons()
		}
		this.view=="Project" ? $(".task-btn").show() : $(".task-btn").hide();
	}

	toggle_toolbar_buttons() {
		this.toggle_shifts_button()
		this.toggle_tasks_button()
	}

	add_view_selector() {
		const view_selectors = {
			"Employee": "users",
			"Department": "oranisation",
			"Project": "project"
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

	change_view(view) {
		this.view = view;
		this.page.standard_actions.empty();
		this.add_view_selector();
		this.toggle_filters();
		this.toggle_toolbar_buttons();
		this.calendar.setOption("resourceAreaColumns", this.get_resource_area_columns())
		this.calendar.refetchResources();
	}

	showPreview(info) {
		this.preview = new EventPreview(info)
	}

	add_filters() {
		this.page.clear_fields();
		this.add_company_filter();
		this.add_department_filter();
		this.add_employee_filter();
		this.add_project_filter();
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
				this.company = this.company_filter.get_value()
			}
		})
	}

	add_department_filter() {
		this.department_filter = this.page.add_field({
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
			hidden: 1,
			change: () => {
				this.department = this.department_filter.get_value()
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
				this.employee = this.employee_filter.get_value()
				this.refetch_all()
			}
		})
	}

	add_project_filter() {
		this.project_filter = this.page.add_field({
			fieldname: "project",
			label: __("Projects"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options('Project', txt);
			},
			hidden: 1,
			change: () => {
				this.projects = this.project_filter.get_value()
				this.remove_tasks_buttons()
				this.add_tasks_buttons()
				// this.refetch_all()
			}
		})
	}

	toggle_department_filter() {
		if (!this.department_filter) {
			this.add_department_filter()
		}
		this.department_filter.toggle(this.view=="Department")
	}

	toggle_project_filter() {
		if (!this.project_filter) {
			this.add_project_filter()
		}
		this.project_filter.toggle(this.view=="Project")
	}

	toggle_filters() {
		this.toggle_department_filter()
		this.toggle_project_filter()
	}

	add_button_group(label, icon, custom_cls) {
		let dropdown_label = `<span class="hidden-xs">
			<span class="custom-btn-group-label">${__(label)}</span>
			${frappe.utils.icon('select', 'xs')}
		</span>`;

		if (icon) {
			dropdown_label = `<span class="hidden-xs">
				${frappe.utils.icon(icon)}
				<span class="custom-btn-group-label">${__(label)}</span>
				${frappe.utils.icon('select', 'xs')}
			</span>
			<span class="visible-xs">
				${frappe.utils.icon(icon)}
			</span>`;
		}

		let custom_btn_group = $(`
			<div class="custom-btn-group ${custom_cls || ''}">
				<button type="button" class="btn btn-default btn-sm ellipsis" data-toggle="dropdown" aria-expanded="false">
					${dropdown_label}
				</button>
				<ul class="dropdown-menu dropdown-menu-right" role="menu"></ul>
			</div>
		`);

		this.page.page_form.append(custom_btn_group);

		return custom_btn_group.find('.dropdown-menu');
	}

	show_quick_entry_form(info, target) {
		frappe.model.with_doctype(target, () => {
			let new_doc = frappe.model.get_new_doc(target);
			new_doc.employee = info.event.getResources().map((resource) => { return resource.id })[0]
			new_doc.shift_type = info.event.extendedProps.reference_name
			new_doc.start_date = moment(info.event.start).format("YYYY-MM-DD")
			new_doc.end_date = moment(info.event.end).format("YYYY-MM-DD")

			frappe.ui.form.make_quick_entry(target, (doc) => {
				// info.event.setProp("id", doc.name)
				frappe.set_route(frappe.get_route_str())
				me.refetch_all();
			}, null, new_doc, true);

			frappe.quick_entry.dialog.get_close_btn().on('click', () => {
				info.revert();
				frappe.quick_entry.dialog.hide();
			});
		});
	}
}


class EventPreview {
	constructor(info) {
		this.info = info
		this.element = $(info.el)
		this.setup_dialog();
	}

	setup_dialog() {
		this.identify_doc();
		this.get_preview_data().then(preview_data => {
			this.init_preview(preview_data)
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

		if (this.info.event.extendedProps.docstatus === 1) {
			this.dialog.set_secondary_action(() => {
				frappe.xcall("frappe.client.cancel", {
					doctype: this.doctype,
					name: this.name
				}).then(r => {
					this.refetch_all()
				})
			});
			this.dialog.set_secondary_action_label(__("Cancel"));
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
		this.name = this.info.event.id;
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

		let dialog_content =`
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
