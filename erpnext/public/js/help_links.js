frappe.provide('frappe.help.help_links');

const lang = frappe.boot.user.language == "fr" ? "/fr/" : "/"
const docsUrl = `https://doc.dokos.io${lang}`;

frappe.help.help_links['Form/Asset'] = [
	{ label: __('Getting started with assets'), url: docsUrl + 'assets/getting-started' },
]