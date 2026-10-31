# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SubscriptionTemplateItem(models.Model):
    """Minimal example model demonstrating Odoo conventions for the subscription template."""
    _name = 'subscription.template.item'
    _description = 'Subscription Template Item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc, id desc'

    name = fields.Char(
        string='Template Name',
        required=True,
        tracking=True,
        help='Descriptive identifier for this template item.'
    )
    code = fields.Char(
        string='Code',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        help='Unique code reference.'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the record without deleting it.'
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        copy=False,
    )
    description = fields.Text(
        string='Description',
        help='Internal notes or additional details.'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'The code must be unique per company!')
    ]

    def action_confirm(self):
        """Transition state from draft to confirmed."""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("Only draft records can be confirmed."))
            record.write({'state': 'confirmed'})
        return True

    def action_reset_to_draft(self):
        """Reset state back to draft."""
        for record in self:
            record.write({'state': 'draft'})
        return True

    def action_cancel(self):
        """Cancel the record."""
        for record in self:
            record.write({'state': 'cancelled'})
        return True
