{{ _("Hello {0},").format(doc.first_name) }}
{% set event = frappe.db.get_value("Event", doc.event, ["route", "subject", "starts_on", "ends_on"], as_dict=True) %}

{{ _("We have received your registration for the event '{0}'").format('<a href="' + frappe.utils.get_url(event.route) + '">' + event.subject + '</a>') }}

{{ _("You were not logged in when you registered, so we are sending you this message to remind you of the details of the event you wish to attend. For your next registration, create an account on <a href='{0}'>our website</a> to manage your registrations more easily.").format(frappe.utils.get_url("")) }}

<a href="{{ frappe.utils.get_url(event.route) }}" style="display: block;">
<ul>
<li><b>{{ event.subject }}</b></li>
<li><b>{{ _("Starts on") }}</b> {{ event.starts_on }}</li>
<li><b>{{ _("Ends on") }}</b> {{ event.ends_on }}</li>
</ul>
</a>

<hr />
{{ _("If you wish to cancel this registration, we suggest you contact us from <a href='{0}'>the contact page</a>.").format(frappe.utils.get_url("/contact")) }}