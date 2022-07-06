# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, add_days, today, nowdate, cstr
from frappe.model.document import Document
from frappe.core.doctype.communication.email import make

class EmailCampaign(Document):
	def validate(self):
		self.set_date()
		#checking if email is set for lead. Not checking for contact as email is a mandatory field for contact.
		if self.email_campaign_for == "Lead":
			self.validate_lead()
		self.validate_email_campaign_already_exists()
		self.update_status()

	def set_date(self):
		if getdate(self.start_date) < getdate(today()):
			frappe.throw(_("Start Date cannot be before the current date"))
		#set the end date as start date + max(send after days) in campaign schedule
		send_after_days = []
		campaign = frappe.get_doc("Campaign", self.campaign_name)
		for entry in campaign.get("campaign_schedules"):
			send_after_days.append(entry.send_after_days)
		try:
			self.end_date = add_days(getdate(self.start_date), max(send_after_days))
		except ValueError:
			frappe.throw(_("Please set up the Campaign Schedule in the Campaign {0}").format(self.campaign_name))

	def validate_lead(self):
		lead_email_id = frappe.db.get_value("Lead", self.recipient, 'email_id')
		if not lead_email_id:
			lead_name = frappe.db.get_value("Lead", self.recipient, 'lead_name')
			frappe.throw(_("Please set an email id for the Lead {0}").format(lead_name))

	def validate_email_campaign_already_exists(self):
		email_campaign_exists = frappe.db.exists("Email Campaign", {
			"campaign_name": self.campaign_name,
			"recipient": self.recipient,
			"status": ("in", ["In Progress", "Scheduled"]),
			"name": ("!=", self.name)
		})
		if email_campaign_exists:
			frappe.throw(_("The Campaign '{0}' already exists for the {1} '{2}'").format(self.campaign_name, self.email_campaign_for, self.recipient))

	def update_status(self):
		start_date = getdate(self.start_date)
		end_date = getdate(self.end_date)
		today_date = getdate(today())
		if start_date > today_date:
			self.status = "Scheduled"
		elif end_date >= today_date:
			self.status = "In Progress"
		elif end_date < today_date:
			self.status = "Completed"

#called through hooks to send campaign mails to leads
def send_email_to_leads_or_contacts():
	email_campaigns = frappe.get_all("Email Campaign", filters = { 'status': ('not in', ['Unsubscribed', 'Completed', 'Scheduled']) })
	for camp in email_campaigns:
		email_campaign = frappe.get_doc("Email Campaign", camp.name)
		campaign = frappe.get_cached_doc("Campaign", email_campaign.campaign_name)
		for entry in campaign.get("campaign_schedules"):
			scheduled_date = add_days(email_campaign.get('start_date'), entry.get('send_after_days'))
			if scheduled_date == getdate(today()):
				send_mail(entry, email_campaign)

def send_email_to_leads_or_contacts_hourly():
	"""This function is called every hour through a hook.

	It sends e-mails from email campaings at a given moment in time,
	specified in the 'send_after' and 'send_at_hour' of the associated
	Email Campaign Schedule child documents of the CRM Campaign.

	Allows up to 60 minutes of lag by design, meaning that e-mails scheduled
	for 9:00 will still be sent at the right time (9:00 + X minutes) if cron
	triggers this function late (at most 60 minutes after 9:00), assuming
	cron triggers it every hour.

	/!\ If any DST or timezone changes happen around the moment an e-mail is
	scheduled, this e-mail can be sent twice or never.
	"""

	import datetime

	def should_send_email_now(dt_base, dt_now=frappe.utils.now_datetime(), precision=3600):
		"""Check that dt_now is between dt_base and dt_base+precision

		NOTE: A necessary condition for the function to return True
		is that `dt_now` should be AFTER `dt_base`.
		In most cases, `dt_now = frappe.utils.now_datetime()`.

		Explanation with simplified examples:
		precision = 1 hours = 60 minutes = 3600 seconds
		+-------------------------------+
		|  now  | base  | delta |  out  |
		|-------+-------+-------+-------|
		| 11:55 | 12:00 | - 5mn | False |
		| 12:00 | 12:00 | + 0mn | True  |
		| 12:05 | 12:00 | + 5mn | True  |
		| 12:55 | 12:00 | +55mn | True  |
		| 13:05 | 12:00 | +65mn | False |
		|-------+-------+-------+-------|
		| 11:55 | 12:30 | -35mn | False |
		| 12:05 | 12:30 | -25mn | False |
		| 12:25 | 12:30 | - 5mn | False |
		| 12:30 | 12:30 | + 0mn | True  |
		| 12:35 | 12:30 | + 5mn | True  |
		| 12:55 | 12:30 | +25mn | True  |
		| 13:05 | 12:30 | +35mn | True  |
		| 13:35 | 12:30 | +65mn | False |
		+-------------------------------+
		"""
		seconds = (dt_now - dt_base).total_seconds()
		_debug(seconds=seconds)
		return 0 <= seconds < precision

	# First, we retrieve all the email campaigns that are In Progress,
	# this includes all the Email Campaigns that must be sent today.

	email_campaigns = frappe.get_all("Email Campaign", filters={
		'status': ('not in', ['Unsubscribed', 'Completed', 'Scheduled'])
	})

	HOUR = 3600  # seconds
	now = frappe.utils.now_datetime()

	for camp in email_campaigns:
		email_campaign = frappe.get_doc("Email Campaign", camp.name)
		campaign = frappe.get_cached_doc("Campaign", email_campaign.campaign_name)

		# Get start_date as a datetime object, time is set to 00:00:00
		d = email_campaign.get('start_date')
		start_date = datetime.datetime(d.year, d.month, d.day)

		for entry in campaign.get("campaign_schedules"):
			# Get the target datetime to send the mail
			# by adding the offsets (days, time) to start_date
			offset_days = entry.get('send_after_days') or 0  # int
			offset_time = entry.get('send_at_time') or datetime.timedelta() # timedelta
			scheduled_date = add_days(start_date, offset_days) + offset_time

			if should_send_email_now(scheduled_date, now, precision=HOUR):
				send_mail(entry, email_campaign)

def send_mail(entry, email_campaign):
	recipient_list = []
	if email_campaign.email_campaign_for == "Email Group":
		for member in frappe.db.get_list("Email Group Member", filters={"email_group": email_campaign.get("recipient")}, fields=["email"]):
			recipient_list.append(member['email'])
	else:
		recipient_list.append(frappe.db.get_value(email_campaign.email_campaign_for, email_campaign.get("recipient"), "email_id"))

	email_template = frappe.get_doc("Email Template", entry.get("email_template"))
	sender = frappe.db.get_value("User", email_campaign.get("sender"), "email")
	context = {"doc": frappe.get_doc(email_campaign.email_campaign_for, email_campaign.recipient)}
	# send mail and link communication to document
	comm = make(
		doctype = "Email Campaign",
		name = email_campaign.name,
		subject = frappe.render_template(email_template.get("subject"), context),
		content = frappe.render_template(email_template.get("response_html") if email_template.use_html else email_template.get("response"), context),
		sender = sender,
		recipients = recipient_list,
		communication_medium = "Email",
		sent_or_received = "Sent",
		send_email = True,
		email_template = email_template.name
	)
	return comm

#called from hooks on doc_event Email Unsubscribe
def unsubscribe_recipient(unsubscribe, method):
	if unsubscribe.reference_doctype == 'Email Campaign':
		frappe.db.set_value("Email Campaign", unsubscribe.reference_name, "status", "Unsubscribed")

#called through hooks to update email campaign status daily
def set_email_campaign_status():
	email_campaigns = frappe.get_all("Email Campaign", filters = { 'status': ('!=', 'Unsubscribed')})
	for entry in email_campaigns:
		email_campaign = frappe.get_doc("Email Campaign", entry.name)
		email_campaign.update_status()
