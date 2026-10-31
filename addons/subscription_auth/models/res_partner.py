# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models


class ResPartner(models.Model):
    """Extend res.partner to identify subscription customers and track status."""
    _inherit = 'res.partner'

    is_subscription_customer = fields.Boolean(
        string='Is Subscription Customer',
        default=False,
        help='Indicates whether this contact holds active or historical subscriptions.'
    )
    subscription_count = fields.Integer(
        string='Subscriptions Count',
        compute='_compute_subscription_count',
        help='Total number of subscriptions linked to this customer.'
    )

    def _compute_subscription_count(self):
        """Placeholder computation to be linked with subscription_management."""
        for partner in self:
            partner.subscription_count = 0
