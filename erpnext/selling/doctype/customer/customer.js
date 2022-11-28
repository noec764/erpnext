// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Customer", {
	setup: function(frm) {

		frm.make_methods = {
			'Quotation': () => frappe.model.open_mapped_doc({
				method: "erpnext.selling.doctype.customer.customer.make_quotation",
				frm: cur_frm
			}),
			'Opportunity': () => frappe.model.open_mapped_doc({
				method: "erpnext.selling.doctype.customer.customer.make_opportunity",
				frm: cur_frm
			})
		}

		frm.add_fetch('lead_name', 'company_name', 'customer_name');
		frm.add_fetch('default_sales_partner','commission_rate','default_commission_rate');
		frm.set_query('customer_group', {'is_group': 0});
		frm.set_query('default_price_list', { 'selling': 1});
		frm.set_query('account', 'accounts', function(doc, cdt, cdn) {
			var d  = locals[cdt][cdn];
			var filters = {
				'account_type': 'Receivable',
				'company': d.company,
				"is_group": 0
			};

			if(doc.party_account_currency) {
				$.extend(filters, {"account_currency": doc.party_account_currency});
			}
			return {
				filters: filters
			}
		});

		if (frm.doc.__islocal == 1) {
			frm.set_value("represents_company", "");
		}

		frm.set_query('customer_primary_contact', function(doc) {
			return {
				query: "erpnext.selling.doctype.customer.customer.get_customer_primary_contact",
				filters: {
					'customer': doc.name
				}
			}
		})
		frm.set_query('customer_primary_address', function(doc) {
			return {
				filters: {
					'link_doctype': 'Customer',
					'link_name': doc.name
				}
			}
		})

		frm.set_query('default_bank_account', function() {
			return {
				filters: {
					'is_company_account': 1
				}
			}
		});

		frm.get_balance = false;
	},
	customer_primary_address: function(frm){
		if(frm.doc.customer_primary_address){
			frappe.call({
				method: 'frappe.contacts.doctype.address.address.get_address_display',
				args: {
					"address_dict": frm.doc.customer_primary_address
				},
				callback: function(r) {
					frm.set_value("primary_address", r.message);
				}
			});
		}
		if(!frm.doc.customer_primary_address){
			frm.set_value("primary_address", "");
		}
	},

	is_internal_customer: function(frm) {
		if (frm.doc.is_internal_customer == 1) {
			frm.toggle_reqd("represents_company", true);
		}
		else {
			frm.toggle_reqd("represents_company", false);
		}
	},

	customer_primary_contact: function(frm){
		if(!frm.doc.customer_primary_contact){
			frm.set_value("mobile_no", "");
			frm.set_value("email_id", "");
		}
	},

	loyalty_program: function(frm) {
		if(frm.doc.loyalty_program) {
			frm.set_value('loyalty_program_tier', null);
		}
	},

	refresh: function(frm) {
		if(frappe.defaults.get_default("cust_master_name")!="Naming Series") {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		frappe.dynamic_link = {doc: frm.doc, fieldname: 'name', doctype: 'Customer'}

		if(!frm.doc.__islocal) {
			frappe.contacts.render_address_and_contact(frm);

			// custom buttons
			frm.add_custom_button(__('Accounts Receivable'), function () {
				frappe.set_route('query-report', 'Accounts Receivable', {customer:frm.doc.name});
			}, __('View'));

			frm.add_custom_button(__('Accounting Ledger'), function () {
				frappe.set_route('query-report', 'General Ledger',
					{party_type: 'Customer', party: frm.doc.name});
			}, __('View'));

			frm.add_custom_button(__('Pricing Rule'), function () {
				erpnext.utils.make_pricing_rule(frm.doc.doctype, frm.doc.name);
			}, __('Create'));

			frm.add_custom_button(__('Get Customer Group Details'), function () {
				frm.trigger("get_customer_group_details");
			}, __('Actions'));

			if (cint(frappe.defaults.get_default("enable_common_party_accounting"))) {
				frm.add_custom_button(__('Link with Supplier'), function () {
					frm.trigger('show_party_link_dialog');
				}, __('Actions'));
			}

			// indicator
			erpnext.utils.set_party_dashboard_indicators(frm);

		} else {
			frappe.contacts.clear_address_and_contact(frm);
		}

		var grid = cur_frm.get_field("sales_team").grid;
		grid.set_column_disp("allocated_amount", false);
		grid.set_column_disp("incentives", false);

		frm.trigger("booking_credits_dashboard");
	},
	validate: function(frm) {
		if(frm.doc.lead_name) frappe.model.clear_doc("Lead", frm.doc.lead_name);

	},
	booking_credits_dashboard: function(frm) {
		return frappe.call({
			method: "erpnext.venue.doctype.booking_credit.booking_credit.has_booking_credits",
			args: {
				customer: frm.doc.name
			}
		}).then(r => {
			if (r.message && !frm.is_new() && !frm.get_balance) {
				frm.get_balance = true
				return frappe.xcall('erpnext.venue.doctype.booking_credit.booking_credit.get_balance', {
					customer: frm.doc.name
				})
			}
		}).then(r => {
			if (!r) {
				return
			}

			const credits = Object.keys(r).map(m => {
				return r[m]
			}).flat().map(d => {
				return d.balance
			});
			const max_count = Math.max.apply(null, credits) > 0 ? Math.max.apply(null, credits) : Math.min.apply(null, credits);

			frm.dashboard.add_section(frappe.render_template('booking_credit_dashboard',
			{
				balance: Object.keys(r).map(f => {
					return flatten_credits(r, f)
				}).flat(),
				customer: frm.doc.name,
				date: frappe.datetime.now_date(),
				max_count: max_count
			}), __("Booking Credits Balance"));
			frm.dashboard.show();
			frm.get_balance = false;

			frm.trigger('bind_reconciliation_btns');
		})
	},
	bind_reconciliation_btns(frm) {
		$(frm.dashboard.wrapper).find('.uom-reconciliation-btn').on("click", e => {
			frappe.xcall("erpnext.venue.page.booking_credits.booking_credits.reconcile_credits", {
				customer: $(e.target).attr("data-customer"),
				target_uom: $(e.target).attr("data-uom"),
				target_item: $(e.target).attr("data-target-item"),
				source_item: $(e.target).attr("data-source-item"),
				date: frm.doc.date
			}).then(r => {
				frappe.show_alert(r)
				frm.refresh()
			})
		})
	},
	get_customer_group_details: function(frm) {
		frappe.call({
			method: "get_customer_group_details",
			doc: frm.doc,
			callback: function() {
				frm.refresh();
			}
		});

	},
	show_party_link_dialog: function(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __('Select a Supplier'),
			fields: [{
				fieldtype: 'Link', label: __('Supplier'),
				options: 'Supplier', fieldname: 'supplier', reqd: 1
			}],
			primary_action: function({ supplier }) {
				frappe.call({
					method: 'erpnext.accounts.doctype.party_link.party_link.create_party_link',
					args: {
						primary_role: 'Customer',
						primary_party: frm.doc.name,
						secondary_party: supplier
					},
					freeze: true,
					callback: function() {
						dialog.hide();
						frappe.msgprint({
							message: __('Successfully linked to Supplier'),
							alert: true
						});
					},
					error: function() {
						dialog.hide();
						frappe.msgprint({
							message: __('Linking to Supplier Failed. Please try again.'),
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

function flatten_credits(obj, item) {
	return obj[item].map(f => {
		return {...f, item: item}
	})
}


frappe.tour["Customer"] = {
	"fr": [
		{
			fieldname: "salutation",
			description: "Civilité pour une personne physique",
		},
		{
			fieldname: "customer_name",
			description: "Ce champ permet d'enregistrer le nom usuel du client, qui peut être différent du nom du document qui est son identifiant de tiers de facturation",
		},
		{
			fieldname: "customer_type",
			description: "Type de client: personne morale (Société) ou personne physique (Individuel)",
		},
		{
			fieldname: "customer_group",
			description: `
				Cette information permet de catégoriser vos clients en groupes/sous-groupes.<br>
				Les catégories permettent notamment de:
					<ul>
						<li>Définir des listes de prix communes</li>
						<li>Définir des modèles de termes de paiement communs</li>
						<li>Définir des comptes centralisateurs par société communs</li>
						<li>Définir règles de limite de crédit communes</li>
						<li>Agréger les données d'achat dans les rapports standards</li>
					</ul>
			`,
		},
		{
			fieldname: "territory",
			description: "Critère de classification du client.<br>Permet notamment de créer des catégories géographiques pour l'analyse des ventes.",
		},
		{
			fieldname: "lead_name",
			description: "Lien vers la fiche **Piste** à partir de laquelle ce client a été créé, le cas échéant.",
		},
		{
			fieldname: "opportunity_name",
			description: "Lien vers la fiche **Opportunité** à partir de laquelle ce client a été créé, le cas échéant.",
		},
		{
			fieldname: "account_manager",
			description: "Utilisateur désigné comme étant responsable de la relation avec ce client.",
		},
		{
			fieldname: "default_price_list",
			description: `Liste de prix définie par défaut pour ce client.<br>
				Si ce champ est vide, le système récupèrera la liste de prix définie dans le groupe de client.<br>
				Si aucune liste de prix n'est définie dans le groupe de client, le système récupèrera la liste de prix par défaut présente dans les paramètres des ventes.
			`,
		},
		{
			fieldname: "default_currency",
			description: "Devise sélectionné par défaut pour ce client dans les transactions.",
		},
		{
			fieldname: "default_bank_account",
			description: "Compte bancaire de la société utilisé par ce client, si votre société possède plusieurs comptes bancaires.",
		},
		{
			fieldname: "is_internal_customer",
			description: `A cocher si le client est une société enregistrée dans Dokos.<br>
				Cela permet de créer des flux de vente inter-société.
			`,
		},
		{
			fieldname: "market_segment",
			description: "Part de marché du client sur son marché.",
		},
		{
			fieldname: "industry",
			description: "Industrie dans laquelle évolue le client.",
		},
		{
			fieldname: "website",
			description: "Site web principal du client.",
		},
		{
			fieldname: "language",
			description: "Langue par défaut du client.<br> Utilisée dans les transactions pour l'impression des documents.",
		},
		{
			fieldname: "customer_details",
			description: "Champ libre pour l'enregistrement d'informations additionnelles pour ce client",
			next_step_tab: "contact_and_address_tab",
		},
		{
			fieldname: "address_html",
			description: "Adresses du client.<br> Vous pouvez créer autant d'adresse que nécessaire.",
			previous_step_tab: "details_tab",
		},
		{
			fieldname: "contact_html",
			description: `Contacts associés au client.<br>
				Si votre client est une personne physique, vous n'aurez probablement qu'un seul contact correspondant à cette personne physique.<br>
				Si votre client est une personne morale, vous pouvez avoir autant de contact que nécessaire.
			`,
		},
		{
			fieldname: "customer_primary_contact",
			description: "Contact principal du client, utilisé notamment dans le point de vente.",
		},
		{
			fieldname: "customer_primary_address",
			description: "Adresse principale du client, utilisée notamment dans le point de vente.",
			next_step_tab: "tax_tab",
		},
		{
			fieldname: "tax_id",
			description: "Numéro de TVA intra-communautaire du client. Peut-être utilisé pour enregistrer un autre numéro fiscal pour les clients hors UE.",
			previous_step_tab: "contact_and_address_tab",
		},
		{
			fieldname: "tax_category",
			description: "Catégorie de taxe à laquelle ce client est associé.<br> Les catégories de taxe permette de créer des règles de détermination de TVA.",
		},
	]
}