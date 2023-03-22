frappe.tour['Booking Credit Usage'] = {
	"fr": [
		{
			fieldname: "user",
			description: "Si renseigné, les crédits seront déduits pour le coupe Client/Utilisateur.<br> Si aucun crédit n'est trouvé pour cet utilisateur, les crédits seront imputés au client."
		},
		{
			fieldname: "customer",
			description: "Le client auquel imputer ces crédits"
		},
		{
			fieldname: "datetime",
			description: "La date/heure à laquelle les crédits ont été déduits"
		},
		{
			fieldname: "booking_credit_type",
			description: "Le type de crédits de réservation à déduire"
		},
		{
			fieldname: "quantity",
			description: "La quantité à déduire"
		},
	]
}