// Copyright (c) 2020, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Booking Credit', {
	onload: function(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Booking Credit Ledger"];
	},
	refresh: function(frm) {
		frm.trigger("add_balance");
	},
	add_balance(frm) {
		if (!frm.is_new && frm.doc.customer) {
			frappe.xcall('erpnext.venue.doctype.booking_credit.booking_credit.get_balance', {
				customer: frm.doc.customer,
				date: frm.doc.date
			}).then(r => {
				const head = Object.keys(r.uom_balance).slice(Math.max(Object.keys(r.uom_balance).length - 5, 0)).map(v => {
					return `<th scope="col">${v}</th>`
					}
				).join("")
				const rows = Object.keys(r.uom_balance).slice(Math.max(Object.keys(r.uom_balance).length - 5, 0)).map(v => {
					return `<th scope="row">${r.uom_balance[v]}</th>`
					}
				).join("")
				const balance = `
					<div><strong>${__("Balance for") + " " + frm.doc.customer_name + " - " + frappe.datetime.global_date_format(frm.doc.date)}</strong></div>
					<div class="mt-2">
						<table class="table">
							<thead>
								<tr>
									${head}
								</tr>
							</thead>
							<tbody>
								<tr>
									${rows}
								</tr>
							</tbody>
						</table>
					</div>
				`
				frm.dashboard.add_section(balance, __("Customer Balance"));
				frm.dashboard.show();
			})
		}
	},
});
