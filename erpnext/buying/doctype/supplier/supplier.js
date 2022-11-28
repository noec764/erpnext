// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Supplier", {
	setup: function (frm) {
		frm.set_query('default_price_list', { 'buying': 1 });
		if (frm.doc.__islocal == 1) {
			frm.set_value("represents_company", "");
		}
		frm.set_query('account', 'accounts', function (doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: {
					'account_type': 'Payable',
					'company': d.company,
					"is_group": 0
				}
			}
		});
		frm.set_query("default_bank_account", function() {
			return {
				filters: {
					"party_type": "Supplier"
				}
			}
		});

		frm.set_query("supplier_primary_contact", function(doc) {
			return {
				query: "erpnext.buying.doctype.supplier.supplier.get_supplier_primary_contact",
				filters: {
					"supplier": doc.name
				}
			};
		});

		frm.set_query("supplier_primary_address", function(doc) {
			return {
				filters: {
					"link_doctype": "Supplier",
					"link_name": doc.name
				}
			};
		});
	},

	refresh: function (frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: 'name', doctype: 'Supplier' }

		if (frappe.defaults.get_default("supp_master_name") != "Naming Series") {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		if (frm.doc.__islocal) {
			hide_field(['address_html','contact_html']);
			frappe.contacts.clear_address_and_contact(frm);
		}
		else {
			unhide_field(['address_html','contact_html']);
			frappe.contacts.render_address_and_contact(frm);

			// custom buttons
			frm.add_custom_button(__('Accounting Ledger'), function () {
				frappe.set_route('query-report', 'General Ledger',
					{ party_type: 'Supplier', party: frm.doc.name });
			}, __("View"));

			frm.add_custom_button(__('Accounts Payable'), function () {
				frappe.set_route('query-report', 'Accounts Payable', { supplier: frm.doc.name });
			}, __("View"));

			frm.add_custom_button(__('Bank Account'), function () {
				erpnext.utils.make_bank_account(frm.doc.doctype, frm.doc.name);
			}, __('Create'));

			frm.add_custom_button(__('Pricing Rule'), function () {
				erpnext.utils.make_pricing_rule(frm.doc.doctype, frm.doc.name);
			}, __('Create'));

			frm.add_custom_button(__('Get Supplier Group Details'), function () {
				frm.trigger("get_supplier_group_details");
			}, __('Actions'));

			if (cint(frappe.defaults.get_default("enable_common_party_accounting"))) {
				frm.add_custom_button(__('Link with Customer'), function () {
					frm.trigger('show_party_link_dialog');
				}, __('Actions'));
			}

			// indicators
			erpnext.utils.set_party_dashboard_indicators(frm);
		}
	},

	get_supplier_group_details: function(frm) {
		frappe.call({
			method: "get_supplier_group_details",
			doc: frm.doc,
			callback: function() {
				frm.refresh();
			}
		});
	},

	supplier_primary_address: function(frm) {
		if (frm.doc.supplier_primary_address) {
			frappe.call({
				method: 'frappe.contacts.doctype.address.address.get_address_display',
				args: {
					"address_dict": frm.doc.supplier_primary_address
				},
				callback: function(r) {
					frm.set_value("primary_address", r.message);
				}
			});
		}
		if (!frm.doc.supplier_primary_address) {
			frm.set_value("primary_address", "");
		}
	},

	supplier_primary_contact: function(frm) {
		if (!frm.doc.supplier_primary_contact) {
			frm.set_value("mobile_no", "");
			frm.set_value("email_id", "");
		}
	},

	is_internal_supplier: function(frm) {
		if (frm.doc.is_internal_supplier == 1) {
			frm.toggle_reqd("represents_company", true);
		}
		else {
			frm.toggle_reqd("represents_company", false);
		}
	},

	show_party_link_dialog: function(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __('Select a Customer'),
			fields: [{
				fieldtype: 'Link', label: __('Customer'),
				options: 'Customer', fieldname: 'customer', reqd: 1
			}],
			primary_action: function({ customer }) {
				frappe.call({
					method: 'erpnext.accounts.doctype.party_link.party_link.create_party_link',
					args: {
						primary_role: 'Supplier',
						primary_party: frm.doc.name,
						secondary_party: customer
					},
					freeze: true,
					callback: function() {
						dialog.hide();
						frappe.msgprint({
							message: __('Successfully linked to Customer'),
							alert: true
						});
					},
					error: function() {
						dialog.hide();
						frappe.msgprint({
							message: __('Linking to Customer Failed. Please try again.'),
							title: __('Linking Failed'),
							indicator: 'red'
						});
					}
				});
			},
			primary_action_label: __('Create Link')
		});
		dialog.show();
	}
});


frappe.tour["Supplier"] = {
	"fr": [
		{
			fieldname: "supplier_name",
			description: "Ce champ permet d'enregistrer le nom usuel du fournisseur, qui peut être différent du nom du document qui est son identifiant de tiers de facturation",
		},
		{
			fieldname: "country",
			description: "Pays d'immatriculation du fournisseur. Vous pouvez enregistrer les différentes adresses du fournisseur dans la section Adresses & Contacts",
		},
		{
			fieldname: "supplier_group",
			description: `
				Cette information permet de catégoriser vos fournisseurs en groupes/sous-groupes.<br>
				Les catégories permettent notamment de:
					<ul>
						<li>Définir des modèles de termes de paiement communs</li>
						<li>Définir des comptes centralisateurs par société communs</li>
						<li>Agréger les données d'achat dans les rapports standards</li>
					</ul>
			`,
		},
		{
			fieldname: "supplier_type",
			description: "Permet de différencier les personnes physiques des personnes morales rapidement.",
		},
		{
			fieldname: "is_transporter",
			description: "Information utilisée pour filtrer les fournisseurs de type *Transporteurs* dans les fiches **Chauffeur** et dans les **bons de livraison**",
		},
		{
			fieldname: "default_currency",
			description: "Devise par défaut utilisée dans les transactions pour ce fournisseur",
		},
		{
			fieldname: "default_price_list",
			description: "Liste de prix par défaut utilisée dans les transactions pour ce fournisseur",
		},
		{
			fieldname: "default_bank_account",
			description: "Compte bancaire par défaut du fournisseur",
		},
		{
			fieldname: "payment_terms",
			description: `
				Modèle de terme de paiement par défaut de ce fournisseur.<br>
				Si ce champ est vide, le modèle de terme de paiement du groupe de fournisseur sera pris en compte.
			`,
		},
		{
			fieldname: "is_internal_supplier",
			description: `A cocher si le fournisseur est une société enregistrée dans Dokos.<br>
				Cela permet de créer des flux d'achat inter-société.
			`,
		},
		{
			fieldname: "supplier_details",
			description: "Information libre",
		},
		{
			fieldname: "language",
			description: "Langue utilisée par défaut pour l'impression et l'envoi de document au fournisseur (Appel d'offre, Commande fournisseur, etc...)",
			next_step_tab: "tax_tab"
		},
		{
			fieldname: "tax_id",
			description: "Numéro de TVA intra-communautaire du fournisseur. Peut-être utilisé pour enregistrer un autre numéro fiscal pour les fournisseurs hors UE.",
			previous_step_tab: "details_tab"
		},
		{
			fieldname: "tax_category",
			description: "Catégorie de taxe à laquelle ce fournisseur est associé.<br> Les catégories de taxe permette de créer des règles de détermination de TVA.",
		},
	]
}