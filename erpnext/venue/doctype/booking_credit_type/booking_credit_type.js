// Copyright (c) 2023, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Booking Credit Type', {
	setup: function(frm) {
		frm.set_query("uom", "conversion_table", function(doc) {
			return {
				query: "erpnext.e_commerce.doctype.website_item.website_item.get_booking_uoms",
			};
		});

		frm.set_query("item", "conversion_table", function(doc) {
			return {
				"filters": {
					"enable_item_booking": 1
				}
			};
		});
	}
});

frappe.tour['Booking Credit Type'] = {
	"fr": [
		{
			fieldname: "label",
			description: "Le libellé de votre type de crédit de réservation. Le libellé vous permet de distinguer facilement vos types de crédits."
		},
		{
			fieldname: "item",
			description: "L'article auquel ce type de crédit de réservation est associé. Le couple Article/Unité de mesure permet au système de déterminer le bon type de crédits à ajouter/déduire."
		},
		{
			fieldname: "uom",
			description: "L'unité de mesure à laquelle ce type de crédits de réservation s'applique. Le couple Article/Unité de mesure permet au système de déterminer le bon type de crédits à ajouter/déduire."
		},
		{
			fieldname: "credits",
			description: "Le nombre de crédits de réservation qu'une unité du couple Article/Unité de mesure permet d'allouer."
		},
		{
			fieldname: "validity",
			description: "Nombre de jours pendant lesquels les crédits alloués sont disponibles avant d'expirer."
		},
		{
			fieldname: "conversion_table",
			description: `
				Ce tableau permet de définir les articles réservables pouvant être échangés contre un crédit de réservation de ce type.<br>
				La conversion se fera toujours pour un couple Article/Unité de mesure.<br>
				Le champ "Crédits" permet de définir un coefficient de conversion.<br>
				Ex. 1 ticket coworking demi-journée peut être échangé contre 4 heures de coworking.
			`
		},
	]
}