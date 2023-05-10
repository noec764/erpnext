def execute():
	"""Set Venue Settings' minute_uom to Minute if unset and the Minute UOM exists"""

	from erpnext.setup.install import set_venue_settings_defaults

	set_venue_settings_defaults()
