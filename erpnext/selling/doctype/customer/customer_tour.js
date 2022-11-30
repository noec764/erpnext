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
		{
			fieldname: "tax_category",
			description: "Catégorie de taxe à laquelle ce client est associé.<br> Les catégories de taxe permette de créer des règles de détermination de TVA.",
		},
		{
			fieldname: "tax_withholding_category",
			description: "Catégorie d'auto-liquidation de taxe à laquelle ce client est associé.",
			next_step_tab: "accounting_tab",
		},
		{
			fieldname: "payment_terms",
			description: "Modèle de termes de paiement à utiliser par défaut pour ce client.",
			previous_step_tab: "tax_tab",
		},
		{
			fieldname: "credit_limits",
			description: "Limites de crédit applicables pour ce client.",
		},
		{
			fieldname: "accounts",
			description: `Compte de tiers auquel affecter ce client.<br>
				Dokos fonctionne avec un compte centralisateur et des comptes auxiliaires correspondant aux identifiants des tiers, ici du client.<br>
				Si vous souhaitez utiliser un compte centralisateur spécifique pour ce client, sélectionnez le dans ce tableau.<br>
				Vous pouvez avoir un compte centralisateur différent par société, en mode multi-société.
			`,
		},
		{
			fieldname: "loyalty_program",
			description: "Programme de fidélité auquel est associé ce client.",
			next_step_tab: "sales_team_tab",
		},
		{
			fieldname: "sales_team",
			description: "Equipe des ventes affectée à ce client et pourcentages à utiliser pour le calcul des commissions.",
			previous_step_tab: "accounting_tab",
		},
		{
			fieldname: "default_sales_partner",
			description: "Partenaire de vente associé à ce client.",
		},
		{
			fieldname: "default_commission_rate",
			description: "Pourcentage de commission par défaut pour ce client.",
			next_step_tab: "settings_tab",
		},
		{
			fieldname: "so_required",
			description: "Paramètre permettant de redéfinir la règle défini dans les paramètres des ventes pour ce client.",
			previous_step_tab: "sales_team_tab",
		},
		{
			fieldname: "dn_required",
			description: "Paramètre permettant de redéfinir la règle défini dans les paramètres des ventes pour ce client.",
		},
		{
			fieldname: "is_frozen",
			description: "Si le tiers est gelé, il ne sera plus possible d'enregistrer d'écriture comptables qui lui sont associées.",
		},
		{
			fieldname: "disabled",
			description: "Si le client est désactivé, il ne sera plus proposé dans les outils de recherche et il ne sera plus possible d'enregistrer de transactions qui lui sont associées.",
		},
	]
}