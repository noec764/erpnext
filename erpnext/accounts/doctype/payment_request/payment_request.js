cur_frm.add_fetch("payment_gateway", "payment_account", "payment_account")
cur_frm.add_fetch("payment_gateway", "payment_gateway", "payment_gateway")
cur_frm.add_fetch("payment_gateway", "message", "message")
cur_frm.add_fetch("payment_gateway", "payment_url_message", "payment_url_message")

frappe.ui.form.on("Payment Request", {
	onload(frm) {
		if (frm.doc.reference_doctype) {
			frappe.call({
				method:"erpnext.accounts.doctype.payment_request.payment_request.get_print_format_list",
				args: {"ref_doctype": frm.doc.reference_doctype},
				callback:function(r){
					set_field_options("print_format", r.message["print_format"])
				}
			})
		}
		if (!frm.is_new() && frm.doc.payment_key) {
			frm.add_web_link(`/payments?link=${frm.doc.payment_key}`);
		}
	},
	refresh(frm) {
		if(frm.doc.status !== "Paid" && !frm.is_new() && frm.doc.docstatus==1){
			frm.add_custom_button(__('Resend Payment Email'), function(){
				frappe.call({
					method: "erpnext.accounts.doctype.payment_request.payment_request.resend_payment_email",
					args: {"docname": frm.doc.name},
					freeze: true,
					freeze_message: __("Sending"),
					callback: function(r){
						if(!r.exc) {
							frappe.msgprint(__("Message Sent"));
						}
					}
				});
			});
		}

		if(!frm.doc.payment_gateway_account && frm.doc.status == "Initiated") {
			frm.add_custom_button(__('Create Payment Entry'), function(){
				frappe.call({
					method: "erpnext.accounts.doctype.payment_request.payment_request.make_payment_entry",
					args: {"docname": frm.doc.name},
					freeze: true,
					callback: function(r){
						if(!r.exc) {
							var doc = frappe.model.sync(r.message);
							frappe.set_route("Form", r.message.doctype, r.message.name);
						}
					}
				});
			}).addClass("btn-primary");
		}
	},
	email_template(frm) {
		frappe.call({
			method: 'frappe.email.doctype.email_template.email_template.get_email_template',
			args: {
				template_name: frm.doc.email_template,
				doc: me.frm.doc
			},
			callback: function(r) {
				if (r.message) {
					console.log(frappe.boot.user.email_signature)
					let signature = frappe.boot.user.email_signature || "";

					if(!frappe.utils.is_html(signature)) {
						signature = signature.replace(/\n/g, "<br>");
					}

					if(r.message.message && signature && r.message.message.includes(signature)) {
						signature = "";
					}
			
					const content = (r.message.message || "") + (signature ? ("<br>" + signature) : "");

					frm.set_value("subject", r.message.subject);
					frm.set_value("message", content);
				}
			}
		});
	},
	payment_gateways_template(frm) {
		if(frm.doc.payment_gateways_template) {
			frappe.model.with_doc("Portal Payment Gateways Template", frm.doc.payment_gateways_template, function() {
				const template = frappe.get_doc("Portal Payment Gateways Template", frm.doc.payment_gateways_template)
				frm.set_value('payment_gateways', template.payment_gateways.slice());
			});
		}
	}

})
