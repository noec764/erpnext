import BankTransactionImporter from './BankTransactionImporter.vue';
frappe.provide("erpnext.bank_transaction")

erpnext.accounts.bankTransactionUpload = class bankTransactionUpload {
	constructor(upload_type) {
		this.data = [];
		this.upload_type = upload_type;
		this.includes_credit_cards = true
		erpnext.bank_transaction = {};

		frappe.utils.make_event_emitter(erpnext.bank_transaction);
		this.make();
	}

	make() {
		this.dialog = new frappe.ui.Dialog({
			size: 'extra-large',
			title: this.upload_type == 'plaid' ? __('Synchronize an account') : __('Upload New Bank Transactions'),
			fields: [
				{
					fieldname: 'transactions',
					label: __('New Transactions'),
					fieldtype: 'HTML'
				},
				{
					fieldname: 'credit_card',
					fieldtype: 'HTML'
				}
			]
		})
		this.dialog.show();
		this.show_uploader();

		erpnext.bank_transaction.on('add_credit_card', (transactions) => {
			const add_text = `<span class="mr-1">${frappe.utils.icon("solid-success", "sm")}</span><span>${__("{0} credit card transactions included in import", [transactions])}</span>`
			const remove_text = `<span class="mr-1">${frappe.utils.icon("solid-warning", "sm")}</span><span>${__("{0} credit card transactions excluded from import", [transactions])}</span>`

			const $credit_card_btn = $(`
				<div class="mt-2 text-center">
					<button class="btn btn-secondary">${this.includes_credit_cards ? add_text : remove_text}</button>
				</div>
			`)

			$credit_card_btn.on("click", () => {
				this.includes_credit_cards = !this.includes_credit_cards
				$credit_card_btn.find(".btn").html(this.includes_credit_cards ? add_text : remove_text)
			})

			this.dialog.fields_dict.credit_card.$wrapper.html($credit_card_btn)
		})

		erpnext.bank_transaction.on('add_primary_action', () => {
			this.dialog.set_primary_action(__("Submit"), () => {
				erpnext.bank_transaction.trigger('add_bank_entries', this.includes_credit_cards)
				this.dialog.disable_primary_action();
			})
		})

		erpnext.bank_transaction.on('add_plaid_action', () => {
			this.dialog.set_primary_action(__("Synchronize"), () => {
				erpnext.bank_transaction.trigger('synchronize_via_plaid')
				this.dialog.disable_primary_action();
			})
		})

		erpnext.bank_transaction.on('close_dialog', () => {
			this.dialog.hide();
			frappe.views.ListView.trigger_list_update({doctype: 'Bank Transaction'});
		})
	}

	show_uploader() {
		this.wrapper = this.dialog.fields_dict.transactions.$wrapper[0];

		frappe.xcall('erpnext.accounts.doctype.bank_transaction.bank_transaction_upload.get_bank_accounts_list')
		.then(r => {
			new Vue({
				el: this.wrapper,
				render: h => h(BankTransactionImporter, {
					props: { upload_type: this.upload_type, bank_accounts: r }
				})
			})
		})
	}
}