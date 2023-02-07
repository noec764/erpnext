<b>{{_("Cancelled event registration needs reimbursement")}}</b>

<h3>{{_("Open Document")}}: {{ frappe.utils.get_link_to_form(doc.doctype, doc.name) }}</h3>

<ul class="list-unstyled">
	<li>{{_("User")}}: <b>{{ doc.contact }} - {{ doc.user }}</b></li>
	<li>{{_("Event")}}: {{ frappe.utils.get_link_to_form("Event", doc.event) }}</li>
	<li>{{ _("Event Registration") }}: {{ frappe.utils.get_link_to_form(doc.doctype, doc.name) }}</li>
</ul>