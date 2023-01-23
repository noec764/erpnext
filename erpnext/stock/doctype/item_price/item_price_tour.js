frappe.tour["Item Price"] = {
    fr: [
        {
            fieldname: "item_code",
            description: "Code de l'article auquel appliquer ce prix"
        },
        {
            fieldname: "uom",
            description: "Unité de mesure pour laquelle appliquer ce prix"
        },
        {
            fieldname: "packing_unit",
            description: "La quantité demandée devra être un multiple de cette valeur pour que le prix soit applicable"
        },
        {
            fieldname: "price_list",
            description: "Liste de prix à laquelle est associée ce prix"
        },
        {
            fieldname: "customer",
            description: "Client auquel s'applique ce prix.<br>Si vous souhaitez appliquer des prix différents à un client pour tous vos articles, vous pouvez aussi créer une liste de prix dédiée."
        },
        {
            fieldname: "batch_no",
            description: "Numéro de lot pour lequel ce prix s'applique"
        },
        {
            fieldname: "price_list_rate",
            description: "Prix unitaire"
        },
        {
            fieldname: "valid_from",
            description: "Date de début de validité de ce prix"
        },
        {
            fieldname: "valid_upto",
            description: "Date de fin de validité de ce prix"
        },
        {
            fieldname: "note",
            description: "Champ permettant d'ajouter une note interne concernant ce prix"
        },
        {
            fieldname: "reference",
            description: "Champ permettant d'ajouter une référence interne associée à ce prix"
        },
    ]
}