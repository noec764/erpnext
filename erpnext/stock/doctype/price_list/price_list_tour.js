frappe.tour["Price List"] = {
    fr: [
        {
            fieldname: "enabled",
            description: "Active/désactive cette liste de prix"
        },
        {
            fieldname: "currency",
            description: "Devise applicable aux prix de cette liste de prix"
        },
        {
            fieldname: "buying",
            description: "Cette liste de prix est applicable aux prix d'achat"
        },
        {
            fieldname: "selling",
            description: "Cette liste de prix est applicable aux prix de vente"
        },
        {
            fieldname: "price_not_uom_dependent",
            description: "Les prix de cette liste de prix ne dépendent pas d'une unité de mesure particulière."
        },
        {
            fieldname: "countries",
            description: "Les prix de cette liste de prix sont uniquement applicables aux pays suivants."
        },
        {
            tour_step_type: "Button",
            button_label: __("Add / Edit Prices"),
            title: __("Add / Edit Prices"),
            description: "Accéder à la liste des prix associés à cette liste de prix."
        }
    ]
}