# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models


class SubscriptionAuditMixin(models.AbstractModel):
    """
    Abstract mixin providing standardized tracking and currency conventions
    across all subscription modules without duplicating field definitions.
    """
    _name = 'subscription.audit.mixin'
    _description = 'Subscription Audit Mixin'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company related to this subscription record.'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
        help='Utility currency field for monetary computations.'
    )
    notes = fields.Html(
        string='Internal Notes',
        help='Internal operational notes and history.'
    )
