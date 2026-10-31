# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class SubscriptionSubscription(models.Model):
    """Extend subscription.subscription with automated invoice generation and billing history."""
    _inherit = 'subscription.subscription'

    invoice_ids = fields.One2many(
        'account.move',
        'subscription_id',
        string='Invoices',
        readonly=True,
    )
    invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_invoice_count',
    )

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for sub in self:
            sub.invoice_count = len(sub.invoice_ids)

    def action_generate_invoice(self):
        """Generate a draft invoice for this subscription."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_("Invoices can only be generated for active subscriptions."))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'subscription_id': self.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                }) for line in self.line_ids
            ],
        }
        invoice = self.env['account.move'].create(invoice_vals)

        # Increment next billing date based on plan interval
        if self.plan_id:
            interval = self.plan_id.billing_interval
            period = self.plan_id.billing_period
            delta = relativedelta(
                days=interval if period == 'daily' else 0,
                weeks=interval if period == 'weekly' else 0,
                months=interval if period == 'monthly' else 0,
                years=interval if period == 'yearly' else 0,
            )
            self.next_billing_date = (self.next_billing_date or fields.Date.context_today(self)) + delta

        return invoice

    @api.model
    def _cron_generate_recurring_invoices(self):
        """Cron task to automatically generate invoices for subscriptions reaching their billing date."""
        today = fields.Date.context_today(self)
        due_subscriptions = self.search([
            ('state', '=', 'active'),
            ('next_billing_date', '<=', today),
        ])
        for subscription in due_subscriptions:
            subscription.action_generate_invoice()
