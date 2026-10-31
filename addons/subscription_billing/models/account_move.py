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
    subscription_calculation_details = fields.Text(
        string='Calculation Snapshot',
        readonly=True,
        copy=False,
        help='JSON snapshot of the invoice calculation at generation time. '
             'Preserves historical prices, discounts, and tax amounts even if '
             'product prices or tax rules change later.',
    )
    subscription_amount_untaxed = fields.Monetary(
        string='Subscription Untaxed Amount',
        readonly=True,
        copy=False,
        help='Snapshotted untaxed amount at invoice generation time.',
    )
    subscription_amount_tax = fields.Monetary(
        string='Subscription Tax Amount',
        readonly=True,
        copy=False,
        help='Snapshotted tax amount at invoice generation time.',
    )
    subscription_amount_total = fields.Monetary(
        string='Subscription Total Amount',
        readonly=True,
        copy=False,
        help='Snapshotted total amount at invoice generation time.',
    )

    @api.depends('subscription_id')
    def _compute_is_subscription_invoice(self):
        for move in self:
            move.is_subscription_invoice = bool(move.subscription_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('subscription_id') and not vals.get('subscription_billing_date'):
                vals['subscription_billing_date'] = vals.get('invoice_date') or fields.Date.context_today(self)
        return super().create(vals_list)

    @api.constrains('subscription_id', 'subscription_billing_date', 'invoice_date', 'state')
    def _check_unique_subscription_billing_cycle(self):
        """Ensure no duplicate invoices exist for the same subscription and billing cycle."""
        for move in self:
            if move.subscription_id and move.state != 'cancel':
                cycle_date = move.subscription_billing_date or move.invoice_date
                if not cycle_date:
                    continue
                duplicate = self.search([
                    ('id', '!=', move.id),
                    ('subscription_id', '=', move.subscription_id.id),
                    ('state', '!=', 'cancel'),
                    '|',
                    ('subscription_billing_date', '=', cycle_date),
                    ('invoice_date', '=', cycle_date),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        "An invoice (%s) has already been generated for subscription '%s' on billing cycle '%s'. "
                        "Duplicate invoices for the same billing cycle are not allowed."
                    ) % (
                        duplicate.name or duplicate.id,
                        move.subscription_id.name,
                        cycle_date,
                    ))
