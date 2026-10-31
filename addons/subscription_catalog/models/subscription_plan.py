# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _


class SubscriptionPlan(models.Model):
    """Defines recurring subscription plans and billing schedules."""
    _name = 'subscription.plan'
    _description = 'Subscription Plan'
    _inherit = ['subscription.audit.mixin', 'mail.thread']
    _order = 'name asc'

    name = fields.Char(
        string='Plan Name',
        required=True,
        tracking=True,
        help='Display name of the subscription plan (e.g., Monthly Pro, Annual Enterprise).'
    )
    code = fields.Char(
        string='Plan Code',
        required=True,
        copy=False,
        help='Unique internal reference identifier for the plan.'
    )
    billing_interval = fields.Integer(
        string='Billing Interval',
        required=True,
        default=1,
        help='Number of billing units per recurring cycle (e.g., 1 month, 3 months).'
    )
    billing_period = fields.Selection(
        selection=[
            ('daily', 'Days'),
            ('weekly', 'Weeks'),
            ('monthly', 'Months'),
            ('yearly', 'Years'),
        ],
        string='Billing Period',
        required=True,
        default='monthly',
        help='Recurring frequency unit.'
    )
    trial_period_days = fields.Integer(
        string='Trial Period (Days)',
        default=0,
        help='Number of free trial days before the first invoice cycle begins.'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to deactivate the plan for new subscriptions.'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'The plan code must be unique per company!')
    ]
