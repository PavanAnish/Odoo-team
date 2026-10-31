# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models


class AccountMove(models.Model):
    """Extend account.move to link customer invoices directly with subscriptions."""
    _inherit = 'account.move'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Originating Subscription',
        readonly=True,
        index=True,
        help='The subscription contract that generated this recurring invoice.'
    )
    is_subscription_invoice = fields.Boolean(
        string='Subscription Invoice',
        compute='_compute_is_subscription_invoice',
        store=True,
        index=True,
    )

    @api.depends('subscription_id')
    def _compute_is_subscription_invoice(self):
        for move in self:
            move.is_subscription_invoice = bool(move.subscription_id)
