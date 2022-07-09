# Copyright (c) 2022, Dokos SAS and Contributors
# License: GNU General Public License v3. See license.txt

from erpnext.regional.france.setup import make_custom_fields


def setup(company=None, patch=True):
	make_custom_fields()
