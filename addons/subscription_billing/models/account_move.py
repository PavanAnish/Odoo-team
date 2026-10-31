# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
    subscription_billing_date = fields.Date(
        string='Billing Cycle Date',
        readonly=True,
        index=True,
        help='The subscription billing cycle date for which this invoice was generated.'
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

    @api.constrains('subscription_id', 'subscription_billing_date', 'state')
    def _check_unique_subscription_billing_cycle(self):
        """Ensure no duplicate invoices exist for the same subscription and billing cycle."""
        for move in self:
            if move.subscription_id and move.subscription_billing_date and move.state != 'cancel':
                duplicate = self.search([
                    ('id', '!=', move.id),
                    ('subscription_id', '=', move.subscription_id.id),
                    ('subscription_billing_date', '=', move.subscription_billing_date),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        "An invoice (%s) has already been generated for subscription '%s' on billing cycle '%s'. "
                        "Duplicate invoices for the same billing cycle are not allowed."
                    ) % (
                        duplicate.name or duplicate.id,
                        move.subscription_id.name,
                        move.subscription_billing_date,
                    ))

