# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Global configuration settings for Subscription Management."""
    _inherit = 'res.config.settings'

    subscription_auto_invoice = fields.Boolean(
        string='Automatic Invoice Generation',
        config_parameter='subscription_base.auto_invoice',
        default=True,
        help='Automatically generate invoices when subscription billing date is reached.'
    )
    subscription_grace_period_days = fields.Integer(
        string='Grace Period (Days)',
        config_parameter='subscription_base.grace_period_days',
        default=5,
        help='Number of days after invoice due date before marking subscription overdue or suspended.'
    )
