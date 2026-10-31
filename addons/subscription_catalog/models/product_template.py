# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models


class ProductTemplate(models.Model):
    """Extend product.template with subscription attributes."""
    _inherit = 'product.template'

    is_subscription_product = fields.Boolean(
        string='Is Subscription Product',
        default=False,
        help='Check this box if this product is sold as a recurring subscription service.'
    )
    subscription_plan_id = fields.Many2one(
        'subscription.plan',
        string='Default Subscription Plan',
        help='Default billing frequency and plan assigned when quoting this product.'
    )
