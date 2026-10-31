# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, tools


class SubscriptionReport(models.Model):
    """Reporting SQL view model for aggregated subscription statistics."""
    _name = 'subscription.report'
    _description = 'Subscription Analytics Report'
    _auto = False
    _order = 'date_start desc'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    plan_id = fields.Many2one('subscription.plan', string='Plan', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    date_start = fields.Date(string='Start Date', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation Sent'),
        ('confirmed', 'Confirmed'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('closed', 'Closed'),
    ], string='Status', readonly=True)
    amount_total = fields.Monetary(string='Recurring Total', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    sub.id AS id,
                    sub.id AS subscription_id,
                    sub.partner_id AS partner_id,
                    sub.plan_id AS plan_id,
                    sub.company_id AS company_id,
                    sub.currency_id AS currency_id,
                    sub.date_start AS date_start,
                    sub.state AS state,
                    sub.amount_total AS amount_total
                FROM subscription_subscription sub
            )
        """ % self._table)
