# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SubscriptionSubscription(models.Model):
    """Core recurring subscription contract model."""
    _name = 'subscription.subscription'
    _description = 'Subscription Contract'
    _inherit = ['subscription.audit.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Subscription Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        domain="[('is_subscription_customer', '=', True)]",
        help='Customer linked to this subscription.'
    )
    plan_id = fields.Many2one(
        'subscription.plan',
        string='Subscription Plan',
        required=True,
        tracking=True,
        help='Plan dictating the billing interval and period.'
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('quotation', 'Quotation Sent'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('closed', 'Closed'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        copy=False,
    )
    date_start = fields.Date(
        string='Start Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    date_end = fields.Date(
        string='End Date',
        help='Optional contract termination date.'
    )
    next_billing_date = fields.Date(
        string='Next Billing Date',
        tracking=True,
        help='Date when the next invoice cycle should be generated.'
    )
    line_ids = fields.One2many(
        'subscription.subscription.line',
        'subscription_id',
        string='Subscription Lines',
        copy=True,
    )
    amount_total = fields.Monetary(
        string='Total Recurring Amount',
        compute='_compute_amount_total',
        store=True,
        tracking=True,
    )

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for sub in self:
            sub.amount_total = sum(sub.line_ids.mapped('price_subtotal'))

    def action_send_quotation(self):
        """Mark quotation as sent."""
        for sub in self:
            if sub.state != 'draft':
                raise ValidationError(_("Only draft subscriptions can be marked as quotation sent."))
            sub.state = 'quotation'
        return True

    def action_confirm(self):
        """Confirm customer agreement and activate subscription."""
        for sub in self:
            if sub.name == _('New'):
                sub.name = self.env['ir.sequence'].next_by_code('subscription.subscription') or _('SUB-%05d') % sub.id
            sub.state = 'active'
            if not sub.next_billing_date:
                sub.next_billing_date = sub.date_start
        return True

    def action_pause(self):
        """Temporarily pause active subscription."""
        for sub in self:
            sub.state = 'paused'
        return True

    def action_resume(self):
        """Resume paused subscription."""
        for sub in self:
            sub.state = 'active'
        return True

    def action_close(self):
        """Terminate / close subscription contract."""
        for sub in self:
            sub.state = 'closed'
            sub.date_end = fields.Date.context_today(self)
        return True


class SubscriptionSubscriptionLine(models.Model):
    """Recurring product lines within a subscription."""
    _name = 'subscription.subscription.line'
    _description = 'Subscription Contract Line'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Subscription',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain="[('is_subscription_product', '=', True)]",
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
    )
    price_unit = fields.Monetary(
        string='Unit Price',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='subscription_id.currency_id',
        string='Currency',
        readonly=True,
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_price_subtotal',
        store=True,
    )

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
