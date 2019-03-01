# Using Custom Domain On Dooks


If you have subscribed to any of the plans at [Dooks](https://dooks.com), you can have us serve your site on your custom domain (for example at http://example.com). This enables your website to be served on a custom domain.

To enable this feature, you will first have to edit DNS settings of your domain as follows.

- Make a CNAME record for a subdomain (www in most cases) to {youraccountname}.dooks.com
- If you want serve the website on a naked domain (ie. http://example.com), set a URL redirect to http://www.example.com and not a CNAME record. Making a CNAME record in this case can have unexpected consequences including you not being able to receive emails anymore.

After you've setup the DNS records, you will have to raise a support ticket by sending an email to support@dooks.com and we'll take it from there.

**Note**: We do not support HTTPS on custom domains. HTTPS enables end to end encryption (from your browser to our server). Although not critical for the website but we strongly recommend against using the Dooks app over an unencrypted protocol. To be safe always use the ERP at your dooks.com address.

