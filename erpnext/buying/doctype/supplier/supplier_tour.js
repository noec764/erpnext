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
		{
			fieldname: "tax_withholding_category",
			description: "Catégorie d'auto-liquidation de taxe à laquelle ce fournisseur est associé.",
			next_step_tab: "contact_and_address_tab",
		},
		{
			fieldname: "address_html",
			description: "Adresses du fournisseur.<br> Vous pouvez créer autant d'adresse que nécessaire.",
			previous_step_tab: "tax_tab",
		},
		{
			fieldname: "contact_html",
			description: `Contacts associés au fournisseur.<br>
				Si votre fournisseur est une personne physique, vous n'aurez probablement qu'un seul contact correspondant à cette personne physique.<br>
				Si votre fournisseur est une personne morale, vous pouvez avoir autant de contact que nécessaire.
			`,
		},
		{
			fieldname: "supplier_primary_contact",
			description: "Contact principal du fournisseur.",
		},
		{
			fieldname: "supplier_primary_address",
			description: "Adresse principale du fournisseur.",
			next_step_tab: "accounting_tab",
		},
		{
			fieldname: "accounts",
			description: `Compte de tiers auquel affecter ce fournisseur.<br>
				Dokos fonctionne avec un compte centralisateur et des comptes auxiliaires correspondant aux identifiants des tiers, ici du fournisseur.<br>
				Si vous souhaitez utiliser un compte centralisateur spécifique pour ce fournisseur, sélectionnez le dans ce tableau.<br>
				Vous pouvez avoir un compte centralisateur différent par société, en mode multi-société.
			`,
			previous_step_tab: "contact_and_address_tab",
			next_step_tab: "settings_tab",
		},
		{
			fieldname: "allow_purchase_invoice_creation_without_purchase_order",
			description: "Paramètre permettant de redéfinir la règle défini dans les paramètres d'achats pour ce fournisseur.",
			previous_step_tab: "accounting_tab",
		},
		{
			fieldname: "allow_purchase_invoice_creation_without_purchase_receipt",
			description: "Paramètre permettant de redéfinir la règle défini dans les paramètres d'achats pour ce fournisseur.",
		},
		{
			fieldname: "is_frozen",
			description: "Si le tiers est gelé, il ne sera plus possible d'enregistrer d'écriture comptables qui lui sont associées.",
		},
		{
			fieldname: "disabled",
			description: "Si le fournisseur est désactivé, il ne sera plus proposé dans les outils de recherche et il ne sera plus possible d'enregistrer de transactions qui lui sont associées.",
		},
		{
			fieldname: "on_hold",
			description: "Si le fournisseur est bloqué, il ne sera plus possible d'enregistrer certaines transactions jusqu'à la date indiquée.",
		},
	]
}