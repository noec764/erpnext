frappe.tour['Booking Credit'] = {
	"fr": [
		{
			fieldname: "date",
			description: "Date de début de validité des crédits"
		},
		{
			fieldname: "expiration_date",
			description: `Si vous ne renseignez rien, la date sera calculée en fonction de la durée prévue dans le type de crédit de réservation sélectionné<br>
			Si vide, les crédits n'auront pas de date d'expiration`
		},
		{
			fieldname: "customer",
			description: "Le client auquel ces crédits seront alloués"
		},
		{
			fieldname: "user",
			description: `Si renseigné, les crédits ne seront utilisables que par cet utilisateur`
		},
		{
			fieldname: "booking_credit_type",
			description: "Le type de crédits de réservation alloué"
		},
		{
			fieldname: "quantity",
			description: "La quantité achetée et allouée au client"
		},
	]
}